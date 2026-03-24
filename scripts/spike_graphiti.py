#!/usr/bin/env python3
"""
Graphiti evaluation spike — test temporal knowledge graph with NotePlan notes.

Compares Graphiti's automatic entity extraction against our current pipeline.
Uses LM Studio for LLM + embeddings (no OpenAI API key needed).

Usage:
    conda run -n knowledge-agents python scripts/spike_graphiti.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# LM Studio config
LM_STUDIO_URL = "http://mac-studio.local:1234/v1"
LM_STUDIO_KEY = "lm-studio"
LLM_MODEL = "qwen3.5-35b-a3b"  # 35B for structured output; 9B fails (routing bug)
EMBED_MODEL = "text-embedding-qwen3-embedding-8b"

# Neo4j
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "knowledge123"

# Graphiti group_id to isolate from existing data
GRAPHITI_GROUP = "graphiti-spike"


async def get_test_sections():
    """Pull 5 sections from existing Neo4j for testing."""
    from neo4j import GraphDatabase

    d = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    sections = []
    with d.session(database="neo4j") as s:
        r = s.run("""
            MATCH (sec:Section)
            WHERE sec.token_count > 150 AND sec.token_count < 400
            AND sec.heading IS NOT NULL AND sec.raw_text IS NOT NULL
            RETURN sec.heading, sec.heading_path, sec.raw_text, sec.token_count, sec.file_path
            ORDER BY rand() LIMIT 5
        """)
        for rec in r:
            sections.append({
                "heading": rec["sec.heading"],
                "heading_path": rec["sec.heading_path"] or "",
                "raw_text": rec["sec.raw_text"],
                "token_count": rec["sec.token_count"],
                "file_path": rec["sec.file_path"] or "",
            })
    d.close()
    return sections


async def run_spike():
    from graphiti_core import Graphiti
    from graphiti_core.llm_client import LLMConfig
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient, DEFAULT_MAX_TOKENS, ModelSize
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    import typing
    from pydantic import BaseModel as PydanticBaseModel
    from openai.types.chat import ChatCompletionMessageParam

    # Custom client for Qwen3.5 on LM Studio:
    # - Do NOT use response_format (json_schema conflicts with thinking mode → empty content)
    # - Instead, let the model think naturally and produce JSON via prompt instruction
    # - Parse JSON from the content field (model produces valid JSON when prompted)

    class LMStudioClient(OpenAIGenericClient):
        async def _generate_response(self, messages, response_model=None, max_tokens=DEFAULT_MAX_TOKENS, model_size=ModelSize.medium):
            import json as json_mod
            import re

            def _extract_json(text: str) -> str:
                """Extract JSON from model output — strip markdown fences, find JSON object."""
                text = text.strip()
                # Strip markdown code fences
                if '```' in text:
                    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
                    if match:
                        text = match.group(1).strip()
                # Find first { ... } block if there's preamble text
                if not text.startswith('{'):
                    idx = text.find('{')
                    if idx >= 0:
                        text = text[idx:]
                # Find matching closing brace
                if text.startswith('{'):
                    depth = 0
                    for i, ch in enumerate(text):
                        if ch == '{': depth += 1
                        elif ch == '}': depth -= 1
                        if depth == 0:
                            return text[:i+1]
                return text

            # Build schema instruction
            schema_instruction = ""
            if response_model is not None:
                schema = response_model.model_json_schema()
                # Simplify schema for the model — show required fields clearly
                schema_instruction = (
                    f"\n\nIMPORTANT: Respond with ONLY a valid JSON object matching this schema. "
                    f"No explanations, no markdown, just the JSON.\n"
                    f"Schema: {json_mod.dumps(schema, indent=2)}"
                )

            openai_messages = []
            for m in messages:
                m.content = self._clean_input(m.content)
                if m.role == 'system' and schema_instruction:
                    m.content += schema_instruction
                openai_messages.append({'role': m.role, 'content': m.content})

            # Try up to 2 times — retry with error feedback
            last_error = None
            for attempt in range(2):
                response = await self.client.chat.completions.create(
                    model=self.model or LLM_MODEL,
                    messages=openai_messages,
                    temperature=self.temperature,
                    max_tokens=max(max_tokens, 8000),
                )

                content = response.choices[0].message.content or ''
                if not content.strip():
                    last_error = ValueError("LLM returned empty content")
                    # Add retry hint
                    openai_messages.append({'role': 'assistant', 'content': ''})
                    openai_messages.append({'role': 'user', 'content': 'Your response was empty. Please output ONLY the JSON object, nothing else.'})
                    continue

                json_str = _extract_json(content)
                try:
                    parsed = json_mod.loads(json_str)
                    # Validate against response_model if provided
                    if response_model is not None:
                        response_model.model_validate(parsed)
                    return parsed
                except (json_mod.JSONDecodeError, Exception) as e:
                    last_error = e
                    # Retry with error feedback
                    openai_messages.append({'role': 'assistant', 'content': content})
                    openai_messages.append({'role': 'user', 'content': f'Your JSON was invalid: {e}. Fix it and respond with ONLY valid JSON.'})
                    continue

            raise last_error or ValueError("Failed to get valid JSON after retries")

    logger.info("=== Graphiti Spike ===")
    logger.info("LLM: %s at %s", LLM_MODEL, LM_STUDIO_URL)
    logger.info("Embedder: %s", EMBED_MODEL)
    logger.info("Group: %s", GRAPHITI_GROUP)

    # Initialize with custom LM Studio client (disables thinking mode)
    llm_client = LMStudioClient(LLMConfig(
        api_key=LM_STUDIO_KEY,
        base_url=LM_STUDIO_URL,
        model=LLM_MODEL,
    ))

    embedder = OpenAIEmbedder(OpenAIEmbedderConfig(
        api_key=LM_STUDIO_KEY,
        base_url=LM_STUDIO_URL,
        model=EMBED_MODEL,
    ))

    # Reranker also needs an LLM — point to LM Studio
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

    # Use a simple reranker that also points to LM Studio
    reranker = OpenAIRerankerClient(LLMConfig(
        api_key=LM_STUDIO_KEY,
        base_url=LM_STUDIO_URL,
        model=LLM_MODEL,
    ))
    # Patch the reranker's client to also disable thinking
    reranker.client = llm_client.client

    graphiti = Graphiti(
        NEO4J_URI, NEO4J_USER, NEO4J_PASS,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=reranker,
    )

    # Build indices
    logger.info("Building Graphiti indices...")
    try:
        await graphiti.build_indices()
        logger.info("Indices built.")
    except Exception as e:
        logger.warning("Index build warning: %s", e)

    # Get test sections
    sections = await get_test_sections()
    logger.info("Got %d test sections", len(sections))

    results = []
    for i, sec in enumerate(sections):
        logger.info("\n--- Section %d: %s (%d tokens) ---", i + 1, sec["heading"][:40], sec["token_count"])
        logger.info("Source: %s", sec["file_path"][:60])

        start = time.monotonic()
        try:
            await graphiti.add_episode(
                name=sec["heading"],
                episode_body=sec["raw_text"],
                source_description=f"NotePlan {sec['file_path']}",
                reference_time=datetime.now(timezone.utc),
                group_id=GRAPHITI_GROUP,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.info("Ingested in %dms", duration_ms)

            results.append({
                "heading": sec["heading"],
                "file_path": sec["file_path"],
                "token_count": sec["token_count"],
                "duration_ms": duration_ms,
                "error": None,
            })

        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error("FAILED in %dms: %s", duration_ms, e)
            results.append({
                "heading": sec["heading"],
                "file_path": sec["file_path"],
                "token_count": sec["token_count"],
                "duration_ms": duration_ms,
                "error": str(e),
            })

    # Search test
    logger.info("\n=== Search Test ===")
    try:
        search_results = await graphiti.search(
            "What tools and technologies are mentioned?",
            group_ids=[GRAPHITI_GROUP],
            num_results=5,
        )
        logger.info("Search returned %d results:", len(search_results))
        for r in search_results:
            logger.info("  %s", str(r)[:100])
    except Exception as e:
        logger.error("Search failed: %s", e)

    # Query graph state
    logger.info("\n=== Graph State ===")
    from neo4j import GraphDatabase
    d = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with d.session(database="neo4j") as s:
        # Count Graphiti entities
        r = s.run("MATCH (n) WHERE n.group_id = $gid RETURN labels(n)[0] AS label, count(n) AS count", gid=GRAPHITI_GROUP)
        for rec in r:
            logger.info("  %s: %d nodes", rec["label"], rec["count"])

        r = s.run("MATCH (n)-[r]->(m) WHERE n.group_id = $gid RETURN type(r) AS type, count(r) AS count", gid=GRAPHITI_GROUP)
        for rec in r:
            logger.info("  %s: %d edges", rec["type"], rec["count"])
    d.close()

    # Summary
    logger.info("\n=== Summary ===")
    ok = [r for r in results if not r["error"]]
    err = [r for r in results if r["error"]]
    avg_ms = sum(r["duration_ms"] for r in ok) / max(len(ok), 1)
    logger.info("Sections: %d/%d succeeded", len(ok), len(results))
    logger.info("Avg latency: %dms", avg_ms)
    if err:
        logger.info("Errors:")
        for e in err:
            logger.info("  %s: %s", e["heading"][:30], e["error"][:80])

    # Save results
    out_path = Path("evals/model_config/results/graphiti_spike.json")
    out_path.write_text(json.dumps(results, indent=2, default=str))
    logger.info("Results saved: %s", out_path)

    await graphiti.close()


if __name__ == "__main__":
    asyncio.run(run_spike())

"""
Graphiti temporal knowledge graph client for the Claude Agent.

Wraps graphiti-core with our LM Studio configuration:
- Extraction LLM: Qwen3.5-35B-A3B (structured JSON output)
- Embeddings: Qwen3-Embedding-8B (4096 dims)
- Neo4j: shared instance with group_id="noteplan"

The custom LMStudioClient bypasses response_format (conflicts with
Qwen3.5 thinking mode) and injects JSON schema into prompts instead.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# LM Studio config
LM_STUDIO_URL = "http://mac-studio.local:1234/v1"
LM_STUDIO_KEY = "lm-studio"
EXTRACTION_MODEL = "qwen3.5-35b-a3b"  # 35B for structured JSON (9B fails)
EMBED_MODEL = "text-embedding-qwen3-embedding-8b"

# Neo4j (same instance as existing, isolated by group_id)
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "knowledge123"

# Group ID to partition Graphiti data
GRAPHITI_GROUP = "noteplan"

_graphiti_instance = None
_initialized = False


def _extract_json(text: str) -> str:
    """Extract JSON object from model output — strips markdown fences, finds {...}."""
    text = text.strip()
    if '```' in text:
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    if not text.startswith('{'):
        idx = text.find('{')
        if idx >= 0:
            text = text[idx:]
    if text.startswith('{'):
        depth = 0
        for i, ch in enumerate(text):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            if depth == 0:
                return text[:i + 1]
    return text


def _create_lm_studio_client():
    """Create a custom LLM client that works with Qwen3.5 on LM Studio."""
    from graphiti_core.llm_client import LLMConfig
    from graphiti_core.llm_client.openai_generic_client import (
        OpenAIGenericClient,
        DEFAULT_MAX_TOKENS,
        ModelSize,
    )

    class LMStudioClient(OpenAIGenericClient):
        """Custom client: injects JSON schema into prompts, retries with error feedback."""

        async def _generate_response(
            self, messages, response_model=None,
            max_tokens=DEFAULT_MAX_TOKENS, model_size=ModelSize.medium,
        ):
            schema_instruction = ""
            if response_model is not None:
                schema = response_model.model_json_schema()
                schema_instruction = (
                    "\n\nIMPORTANT: Respond with ONLY a valid JSON object matching this schema. "
                    "No explanations, no markdown, just the JSON.\n"
                    f"Schema: {json.dumps(schema, indent=2)}"
                )

            openai_messages = []
            for m in messages:
                m.content = self._clean_input(m.content)
                if m.role == 'system' and schema_instruction:
                    m.content += schema_instruction
                openai_messages.append({'role': m.role, 'content': m.content})

            last_error = None
            for attempt in range(2):
                response = await self.client.chat.completions.create(
                    model=self.model or EXTRACTION_MODEL,
                    messages=openai_messages,
                    temperature=self.temperature,
                    max_tokens=max(max_tokens, 8000),
                )

                content = response.choices[0].message.content or ''
                if not content.strip():
                    last_error = ValueError("LLM returned empty content")
                    openai_messages.append({'role': 'assistant', 'content': ''})
                    openai_messages.append({'role': 'user', 'content': 'Your response was empty. Please output ONLY the JSON object.'})
                    continue

                json_str = _extract_json(content)
                try:
                    parsed = json.loads(json_str)
                    if response_model is not None:
                        response_model.model_validate(parsed)
                    return parsed
                except (json.JSONDecodeError, Exception) as e:
                    last_error = e
                    openai_messages.append({'role': 'assistant', 'content': content})
                    openai_messages.append({'role': 'user', 'content': f'Your JSON was invalid: {e}. Fix it and respond with ONLY valid JSON.'})
                    continue

            raise last_error or ValueError("Failed to get valid JSON after retries")

    return LMStudioClient(LLMConfig(
        api_key=LM_STUDIO_KEY,
        base_url=LM_STUDIO_URL,
        model=EXTRACTION_MODEL,
    ))


async def get_graphiti():
    """Get or initialize the Graphiti client. Returns None on failure (graceful degradation)."""
    global _graphiti_instance, _initialized

    if _initialized:
        return _graphiti_instance

    _initialized = True

    try:
        from graphiti_core import Graphiti
        from graphiti_core.llm_client import LLMConfig
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
        from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

        llm_client = _create_lm_studio_client()

        embedder = OpenAIEmbedder(OpenAIEmbedderConfig(
            api_key=LM_STUDIO_KEY,
            base_url=LM_STUDIO_URL,
            model=EMBED_MODEL,
        ))

        reranker = OpenAIRerankerClient(LLMConfig(
            api_key=LM_STUDIO_KEY,
            base_url=LM_STUDIO_URL,
            model=EXTRACTION_MODEL,
        ))
        reranker.client = llm_client.client

        _graphiti_instance = Graphiti(
            NEO4J_URI, NEO4J_USER, NEO4J_PASS,
            llm_client=llm_client,
            embedder=embedder,
            cross_encoder=reranker,
        )

        logger.info("Graphiti initialized — LLM=%s, group=%s", EXTRACTION_MODEL, GRAPHITI_GROUP)

    except ImportError:
        logger.info("graphiti-core not installed — Graphiti disabled")
        _graphiti_instance = None
    except Exception as e:
        logger.warning("Graphiti initialization failed: %s — disabled", e)
        _graphiti_instance = None

    return _graphiti_instance


async def close_graphiti():
    """Shutdown Graphiti client."""
    global _graphiti_instance, _initialized
    if _graphiti_instance:
        try:
            await _graphiti_instance.close()
        except Exception:
            pass
    _graphiti_instance = None
    _initialized = False

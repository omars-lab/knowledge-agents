#!/usr/bin/env python3
"""
Section-level indexing pipeline for NotePlan notes.

Parses notes into sections, optionally summarizes via local LLM,
generates embeddings, and stores in Qdrant + Neo4j.

Usage:
    python scripts/seed_sections.py --noteplan-dir /noteplan
    python scripts/seed_sections.py --noteplan-dir /noteplan --summarize --concurrency 3
    python scripts/seed_sections.py --noteplan-dir /noteplan --full-reindex
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from neo4j import GraphDatabase
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from knowledge_agents.notes.parser import read_noteplan_file
from knowledge_agents.notes.traversal import get_files_from_last_month
from knowledge_agents.types.section import PipelineStats, SectionData
from knowledge_agents.utils.delta_tracker import compute_delta, get_indexed_hashes
from knowledge_agents.utils.graph_utils import (
    create_section_nodes,
    link_section_entities,
    setup_graph_schema,
)
from knowledge_agents.utils.text_splitters import split_content_into_sections
from knowledge_agents.utils.vector_store_utils import estimate_tokens

logger = logging.getLogger(__name__)

# Defaults
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
SECTIONS_COLLECTION = "sections_collection"
EMBEDDING_DIMS = 4096
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "knowledge123"
NEO4J_DB = "neo4j"
LITELLM_URL = "http://localhost:4000/v1"
LITELLM_KEY = "sk-1234"
EMBED_MODEL = "lm_studio/text-embedding-qwen3-embedding-8b"


def _content_hash(content: str) -> str:
    """SHA256 hash of file content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ── Phase A: Parse ──────────────────────────────────────────────────────

def phase_parse(
    files: list[tuple[Path, str]],
    noteplan_dir: Path,
    stats: PipelineStats,
) -> list[SectionData]:
    """Parse all files into sections."""
    all_sections: list[SectionData] = []

    for file_path, content_hash in files:
        try:
            relative = str(file_path.relative_to(noteplan_dir))
        except ValueError:
            relative = str(file_path)

        try:
            content = read_noteplan_file(file_path)
            if not content.strip():
                stats.files_skipped += 1
                continue

            sections = split_content_into_sections(content, file_path=file_path)

            for sec in sections:
                token_count = estimate_tokens(sec["content"])
                all_sections.append(SectionData(
                    file_path=relative,
                    section_index=sec["section_index"],
                    heading=sec.get("heading"),
                    heading_level=sec.get("heading_level"),
                    heading_path=sec.get("heading_path", ""),
                    raw_text=sec["content"],
                    token_count=token_count,
                    content_hash=content_hash,
                ))

        except Exception as e:
            stats.errors.append(f"Parse error {relative}: {e}")
            logger.warning("Failed to parse %s: %s", relative, e)

    stats.sections_total = len(all_sections)
    return all_sections


# ── Phase B: Summarize ──────────────────────────────────────────────────

async def phase_summarize(
    sections: list[SectionData],
    stats: PipelineStats,
    model: str = "qwen3.5-35b-a3b",
    concurrency: int = 3,
    min_tokens: int = 200,
    delay: float = 0.5,
) -> list[SectionData]:
    """Summarize all sections via LLM."""
    from knowledge_agents.services.summarizer import summarize_sections_batch

    result = await summarize_sections_batch(
        sections,
        model=model,
        proxy_url=LITELLM_URL,
        proxy_key=LITELLM_KEY,
        concurrency=concurrency,
        min_tokens=min_tokens,
        delay_between_batches=delay,
    )

    stats.sections_summarized = sum(1 for s in result if s.summary is not None)
    stats.sections_skipped_summary = len(result) - stats.sections_summarized
    return result


# ── Phase C: Embed ──────────────────────────────────────────────────────

def phase_embed(
    sections: list[SectionData],
    stats: PipelineStats,
    batch_size: int = 10,
    delay: float = 0.5,
) -> list[SectionData]:
    """Generate embeddings for all sections."""
    client = OpenAI(base_url=LITELLM_URL, api_key=LITELLM_KEY)

    for i in range(0, len(sections), batch_size):
        batch = sections[i : i + batch_size]
        texts = [s.embedding_text for s in batch]

        try:
            response = client.embeddings.create(input=texts, model=EMBED_MODEL)
            for j, emb_data in enumerate(response.data):
                batch[j].embedding = emb_data.embedding
                stats.sections_embedded += 1
        except Exception as e:
            stats.errors.append(f"Embedding batch {i // batch_size}: {e}")
            logger.warning("Embedding batch failed: %s", e)

        if i + batch_size < len(sections) and delay > 0:
            time.sleep(delay)

    return sections


# ── Phase D: Store ──────────────────────────────────────────────────────

def phase_store(
    sections: list[SectionData],
    stats: PipelineStats,
    qdrant: QdrantClient,
    neo4j_driver,
) -> None:
    """Store sections in Qdrant and Neo4j."""
    # Group sections by file
    by_file: dict[str, list[SectionData]] = {}
    for s in sections:
        by_file.setdefault(s.file_path, []).append(s)

    # Get all entity names for linking
    entity_names: list[str] = []
    try:
        with neo4j_driver.session(database=NEO4J_DB) as session:
            result = session.run("MATCH (e:Entity) RETURN e.name AS name")
            entity_names = [r["name"] for r in result]
    except Exception as e:
        logger.warning("Failed to fetch entity names: %s", e)

    for file_path, file_sections in by_file.items():
        # ── Qdrant: upsert section vectors ──
        points = []
        for s in file_sections:
            if s.embedding is None:
                continue
            point_id = hashlib.md5(s.section_id.encode()).hexdigest()
            # Qdrant needs UUID-compatible IDs — use first 32 hex chars
            points.append(PointStruct(
                id=point_id,
                vector=s.embedding,
                payload={
                    "file_path": s.file_path,
                    "section_index": s.section_index,
                    "heading": s.heading,
                    "heading_level": s.heading_level,
                    "heading_path": s.heading_path,
                    "has_summary": s.summary is not None,
                    "token_count": s.token_count,
                    "content_hash": s.content_hash,
                },
            ))

        if points:
            try:
                qdrant.upsert(collection_name=SECTIONS_COLLECTION, points=points)
            except Exception as e:
                stats.errors.append(f"Qdrant upsert {file_path}: {e}")
                logger.warning("Qdrant upsert failed for %s: %s", file_path, e)

        # ── Neo4j: create Section nodes ──
        section_dicts = [
            {
                "section_id": s.section_id,
                "section_index": s.section_index,
                "heading": s.heading,
                "heading_level": s.heading_level,
                "heading_path": s.heading_path,
                "raw_text": s.raw_text,
                "summary": s.summary,
                "token_count": s.token_count,
                "content_hash": s.content_hash,
            }
            for s in file_sections
        ]

        try:
            create_section_nodes(neo4j_driver, file_path, section_dicts, NEO4J_DB)
        except Exception as e:
            stats.errors.append(f"Neo4j sections {file_path}: {e}")
            logger.warning("Neo4j section create failed for %s: %s", file_path, e)

        # ── Update Note.content_hash ──
        if file_sections:
            try:
                with neo4j_driver.session(database=NEO4J_DB) as session:
                    session.run(
                        "MATCH (n:Note {file_path: $fp}) SET n.content_hash = $hash",
                        fp=file_path,
                        hash=file_sections[0].content_hash,
                    )
            except Exception:
                pass  # non-critical

        # ── Link sections to entities ──
        if entity_names:
            entity_set = set(entity_names)
            for s in file_sections:
                # Simple substring match: find entity names in section text
                found = [name for name in entity_set if name.lower() in s.raw_text.lower()]
                if found:
                    try:
                        linked = link_section_entities(neo4j_driver, s.section_id, found, NEO4J_DB)
                        stats.entities_linked += linked
                    except Exception:
                        pass  # non-critical


# ── Main ────────────────────────────────────────────────────────────────

async def seed_sections(
    noteplan_dir: Path,
    full_reindex: bool = False,
    summarize: bool = False,
    concurrency: int = 3,
    embedding_batch_size: int = 10,
    delay: float = 0.5,
    summarize_model: str = "qwen3.5-35b-a3b",
) -> PipelineStats:
    """Main pipeline: parse → summarize → embed → store."""
    stats = PipelineStats()
    start = time.monotonic()

    # ── Init clients ──
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

    # Ensure Qdrant collection exists
    collections = [c.name for c in qdrant.get_collections().collections]
    if SECTIONS_COLLECTION not in collections:
        qdrant.create_collection(
            collection_name=SECTIONS_COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIMS, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection: %s", SECTIONS_COLLECTION)

    # Ensure Neo4j schema
    setup_graph_schema(neo4j_driver, NEO4J_DB)

    # ── Discover files ──
    print("📁 Discovering files...")
    all_files = get_files_from_last_month(noteplan_dir)
    stats.files_discovered = len(all_files)

    # ── Delta detection ──
    if full_reindex:
        files_to_index = [(fp, _content_hash(read_noteplan_file(fp))) for fp, _ in all_files]
        stats.files_changed = len(files_to_index)
    else:
        indexed_hashes = get_indexed_hashes(neo4j_driver, NEO4J_DB)
        # compute_delta expects (Path, mtime) tuples, returns (Path, hash) tuples
        files_with_hashes = []
        for fp, mtime in all_files:
            try:
                content = read_noteplan_file(fp)
                files_with_hashes.append((fp, _content_hash(content)))
            except Exception:
                pass
        # Simple delta: compare hashes
        files_to_index = []
        for fp, h in files_with_hashes:
            try:
                relative = str(fp.relative_to(noteplan_dir))
            except ValueError:
                relative = str(fp)
            if indexed_hashes.get(relative) != h:
                files_to_index.append((fp, h))
        stats.files_changed = len(files_to_index)
        stats.files_skipped = stats.files_discovered - stats.files_changed

    print(f"  Found {stats.files_discovered} files, {stats.files_changed} changed\n")

    if not files_to_index:
        print("✅ No files to index (all up to date)")
        stats.duration_seconds = time.monotonic() - start
        neo4j_driver.close()
        return stats

    # ── Phase A: Parse ──
    print("📝 Phase A: Parsing sections...")
    all_sections = phase_parse(files_to_index, noteplan_dir, stats)
    print(f"  {stats.files_changed} files → {stats.sections_total} sections\n")

    if not all_sections:
        print("✅ No sections to process")
        stats.duration_seconds = time.monotonic() - start
        neo4j_driver.close()
        return stats

    # ── Phase B: Summarize (optional) ──
    if summarize:
        print(f"🧠 Phase B: Summarizing ({summarize_model.split('/')[-1]})...")
        all_sections = await phase_summarize(
            all_sections, stats,
            model=summarize_model,
            concurrency=concurrency,
            delay=delay,
        )
        print(f"  {stats.sections_summarized} summarized, {stats.sections_skipped_summary} skipped\n")
    else:
        print("⏭️  Phase B: Summarization skipped (use --summarize to enable)\n")

    # ── Phase C: Embed ──
    print(f"🔢 Phase C: Embedding ({EMBED_MODEL.split('/')[-1]})...")
    all_sections = phase_embed(all_sections, stats, batch_size=embedding_batch_size, delay=delay)
    print(f"  {stats.sections_embedded} sections embedded\n")

    # ── Phase D: Store ──
    print("💾 Phase D: Storing...")
    phase_store(all_sections, stats, qdrant, neo4j_driver)
    print(f"  Qdrant: {stats.sections_embedded} points → {SECTIONS_COLLECTION}")
    print(f"  Neo4j: {stats.sections_total} Section nodes, {stats.entities_linked} entity links\n")

    stats.duration_seconds = time.monotonic() - start
    neo4j_driver.close()

    # ── Summary ──
    print(f"✅ Done in {stats.duration_seconds:.1f}s")
    print(f"   {stats.sections_total} sections | {stats.files_changed} files | {stats.entities_linked} entity links")
    if stats.errors:
        print(f"   ⚠️  {len(stats.errors)} errors:")
        for err in stats.errors[:5]:
            print(f"      {err}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Section-level note indexing pipeline")
    parser.add_argument("--noteplan-dir", type=Path, required=True, help="NotePlan root directory")
    parser.add_argument("--summarize", action="store_true", help="Enable LLM summarization")
    parser.add_argument("--summarize-model", default="qwen3.5-35b-a3b", help="Model for summarization")
    parser.add_argument("--full-reindex", action="store_true", help="Re-index all files (ignore delta)")
    parser.add_argument("--concurrency", type=int, default=3, help="Max parallel LLM calls (default: 3)")
    parser.add_argument("--batch-size", type=int, default=10, help="Embedding batch size (default: 10)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between batches in seconds (default: 0.5)")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    asyncio.run(seed_sections(
        noteplan_dir=args.noteplan_dir,
        full_reindex=args.full_reindex,
        summarize=args.summarize,
        concurrency=args.concurrency,
        embedding_batch_size=args.batch_size,
        delay=args.delay,
        summarize_model=args.summarize_model,
    ))


if __name__ == "__main__":
    main()

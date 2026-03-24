"""
MCP tools for the Claude Agent.

Provides tools registered as an in-process MCP server:
- read_note: Read a NotePlan markdown file
- build_knowledge_graph: Extract entities/relationships to Neo4j
- query_knowledge_graph: Execute Cypher queries against Neo4j
- derive_xcallback_url: Generate NotePlan x-callback-url links
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import requests
from claude_agent_sdk import create_sdk_mcp_server, tool
from neo4j import GraphDatabase
from openai import OpenAI
from qdrant_client import QdrantClient

from .graphiti_client import get_graphiti, GRAPHITI_GROUP
from ..utils.graph_utils import setup_graph_schema  # Still needed for Neo4j index setup

from .config import ClaudeAgentSettings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared clients — initialized once via init_tool_clients()
# ---------------------------------------------------------------------------

_qdrant_client: QdrantClient | None = None
_embedding_client: OpenAI | None = None
_neo4j_driver: GraphDatabase.driver | None = None
_settings: ClaudeAgentSettings | None = None
_neo4j_schema_initialized: bool = False


def init_tool_clients(settings: ClaudeAgentSettings) -> None:
    """Initialize shared clients used by all tools. Call once at startup."""
    global _qdrant_client, _embedding_client, _neo4j_driver, _settings

    _settings = settings

    # Qdrant
    logger.info("Connecting to Qdrant at %s:%s...", settings.qdrant_host, settings.qdrant_port)
    _qdrant_client = QdrantClient(
        host=settings.qdrant_host, port=settings.qdrant_port
    )
    try:
        collections = _qdrant_client.get_collections().collections
        names = [c.name for c in collections]
        logger.info("Qdrant connected — collections: %s", names)
        if settings.qdrant_collection_name not in names:
            logger.warning(
                "Target collection '%s' not found in Qdrant. semantic_search will fail until data is seeded.",
                settings.qdrant_collection_name,
            )
    except Exception:
        logger.warning("Qdrant connection check failed — searches may fail", exc_info=True)

    # Embedding client — disabled until embedding provider is configured (task #20)
    # Uncomment when semantic_search is re-enabled with Voyage AI or another provider.
    # if settings.embedding_provider == "proxy":
    #     embed_url = f"http://{settings.litellm_proxy_host}:{settings.litellm_proxy_port}/v1"
    #     _embedding_client = OpenAI(base_url=embed_url, api_key=settings.litellm_proxy_api_key)
    # else:
    #     _embedding_client = OpenAI()

    # Neo4j
    logger.info("Connecting to Neo4j at %s...", settings.neo4j_uri)
    _neo4j_driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    try:
        _neo4j_driver.verify_connectivity()
        logger.info("Neo4j connected — database=%s", settings.neo4j_database)
        # Initialize schema at startup (idempotent) so it doesn't block tool calls
        setup_graph_schema(_neo4j_driver, settings.neo4j_database)
        _neo4j_schema_initialized = True
        logger.info("Neo4j schema initialized")
    except Exception:
        logger.warning("Neo4j connection/schema check failed — graph tools may fail", exc_info=True)


def close_tool_clients() -> None:
    """Close shared clients. Call on shutdown."""
    global _qdrant_client, _neo4j_driver
    if _neo4j_driver:
        _neo4j_driver.close()
        _neo4j_driver = None
    _qdrant_client = None


def _generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for the given text.

    Uses the configured embedding provider (LiteLLM proxy or OpenAI).
    Raises TimeoutError if the embedding service is unreachable.
    """
    import signal

    def _timeout_handler(signum, frame):
        raise TimeoutError("Embedding service did not respond within 15 seconds")

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(15)
    try:
        result = _embedding_client.embeddings.create(
            input=[text],
            model=_settings.litellm_proxy_embedding_model,
        )
        return result.data[0].embedding
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def _ensure_neo4j_schema() -> None:
    """Ensure Neo4j schema is set up (idempotent, called on first graph write)."""
    global _neo4j_schema_initialized
    if not _neo4j_schema_initialized and _neo4j_driver:
        setup_graph_schema(_neo4j_driver, _settings.neo4j_database)
        _neo4j_schema_initialized = True


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@tool(
    name="semantic_search",
    description=(
        "Search NotePlan notes by semantic similarity. "
        "Returns ranked file paths with similarity scores. "
        "Use this to find notes relevant to a topic or question."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results (default 5)",
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
    },
)
async def semantic_search(args: dict[str, Any]) -> dict[str, Any]:
    """Search notes via Qdrant vector store."""
    query = args["query"]
    limit = args.get("limit", _settings.semantic_search_limit)

    try:
        query_vector = _generate_embedding(query)

        search_results = _qdrant_client.search(
            collection_name=_settings.qdrant_collection_name,
            query_vector=query_vector,
            limit=limit,
        )

        results = []
        for result in search_results:
            payload = result.payload
            results.append({
                "file_path": payload.get("file_path", ""),
                "file_name": payload.get("file_name", ""),
                "modified_at": payload.get("modified_at", ""),
                "file_size": payload.get("file_size", 0),
                "similarity_score": round(float(result.score), 4),
            })

        text = json.dumps(results, indent=2)
        logger.info(
            "semantic_search for '%s' returned %d results", query[:50], len(results)
        )
        return {"content": [{"type": "text", "text": text}]}

    except TimeoutError as e:
        logger.error("semantic_search timed out: %s", e)
        return {
            "content": [{
                "type": "text",
                "text": (
                    "Embedding service is unavailable (timed out after 15s). "
                    "Semantic search requires a running embedding service. "
                    "Let the user know that search is currently unavailable and "
                    "offer to help with other tools (read_note, knowledge graph)."
                ),
            }],
            "is_error": True,
        }
    except Exception as e:
        logger.error("semantic_search error: %s", e, exc_info=True)
        return {
            "content": [{"type": "text", "text": f"Error performing search: {e}"}],
            "is_error": True,
        }


@tool(
    name="read_note",
    description=(
        "Read the full text content of a NotePlan markdown file. "
        "Use a file_path from semantic_search results."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Relative file path (e.g. '2025-01-15.md' or 'Notes/project.md')",
            },
        },
        "required": ["file_path"],
    },
)
async def read_note(args: dict[str, Any]) -> dict[str, Any]:
    """Read a NotePlan file from the mounted noteplan directory."""
    from ..notes.parser import read_noteplan_file

    file_path = args["file_path"]

    try:
        full_path = Path(_settings.noteplan_dir) / file_path
        content = read_noteplan_file(full_path)
        logger.info("read_note: read %d chars from %s", len(content), file_path)
        return {"content": [{"type": "text", "text": content}]}

    except Exception as e:
        logger.error("read_note error for %s: %s", file_path, e)
        return {
            "content": [{"type": "text", "text": f"Error reading note: {e}"}],
            "is_error": True,
        }


@tool(
    name="build_knowledge_graph",
    description=(
        "Build a temporal knowledge graph from note content using Graphiti. "
        "Graphiti automatically extracts entities and relationships — you just "
        "provide the file_path and note content. Entities are deduplicated, "
        "relationships get temporal validity tracking, and everything is searchable "
        "via hybrid (semantic + keyword + graph) search."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Relative path of the note file being processed",
            },
            "note_content": {
                "type": "string",
                "description": "The full text content of the note to extract entities from. If not provided, the tool will read the file.",
            },
        },
        "required": ["file_path"],
    },
)
async def build_knowledge_graph(args: dict[str, Any]) -> dict[str, Any]:
    """Ingest a note as a Graphiti episode — automatic entity/relationship extraction."""
    from datetime import datetime, timezone

    file_path = args["file_path"]
    note_content = args.get("note_content")

    try:
        # Read note content if not provided
        if not note_content:
            from ..notes.parser import read_noteplan_file
            full_path = Path(_settings.noteplan_dir) / file_path
            note_content = read_noteplan_file(full_path)

        graphiti = await get_graphiti()
        if not graphiti:
            return {
                "content": [{"type": "text", "text": "Graphiti is not available. Check LM Studio status."}],
                "is_error": True,
            }

        await graphiti.add_episode(
            name=file_path,
            episode_body=note_content,
            source_description=f"NotePlan {file_path}",
            reference_time=datetime.now(timezone.utc),
            group_id=GRAPHITI_GROUP,
        )

        summary = (
            f"Knowledge graph updated for '{file_path}' via Graphiti. "
            f"Entities and temporal relationships extracted automatically."
        )
        logger.info(summary)
        return {"content": [{"type": "text", "text": summary}]}

    except Exception as e:
        logger.error("build_knowledge_graph error: %s", e, exc_info=True)
        return {
            "content": [{"type": "text", "text": f"Error building graph: {e}"}],
            "is_error": True,
        }


@tool(
    name="query_knowledge_graph",
    description=(
        "Search the temporal knowledge graph using Graphiti's hybrid search "
        "(semantic + keyword + graph traversal). Returns entities, relationships, "
        "and facts with temporal validity. Use natural language queries — "
        "Graphiti handles the search strategy automatically."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query (e.g., 'What tools does Omar use?')",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return (default 10)",
                "minimum": 1,
                "maximum": 50,
            },
        },
        "required": ["query"],
    },
)
async def query_knowledge_graph(args: dict[str, Any]) -> dict[str, Any]:
    """Search the knowledge graph via Graphiti hybrid search."""
    search_query = args["query"]
    limit = args.get("limit", 10)

    try:
        graphiti = await get_graphiti()
        if not graphiti:
            return {
                "content": [{"type": "text", "text": "Graphiti is not available. Check LM Studio status."}],
                "is_error": True,
            }

        results = await graphiti.search(
            search_query,
            group_ids=[GRAPHITI_GROUP],
            num_results=limit,
        )

        if not results:
            return {"content": [{"type": "text", "text": f"No results found for: {search_query}"}]}

        # Format results for the agent
        formatted = []
        for r in results:
            formatted.append(str(r))

        text = f"Found {len(results)} results:\n\n" + "\n\n".join(formatted)
        logger.info("query_knowledge_graph returned %d results for: %s", len(results), search_query[:60])
        return {"content": [{"type": "text", "text": text}]}

    except Exception as e:
        logger.error("query_knowledge_graph error: %s", e, exc_info=True)
        return {
            "content": [{"type": "text", "text": f"Error searching graph: {e}"}],
            "is_error": True,
        }


@tool(
    name="query_graph_cypher",
    description=(
        "Execute a raw Cypher query against Neo4j (advanced). "
        "Use query_knowledge_graph for most searches — this is for "
        "when you need specific Cypher patterns. Read-only queries only."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "cypher_query": {
                "type": "string",
                "description": "A read-only Cypher query (MATCH/RETURN only)",
            },
        },
        "required": ["cypher_query"],
    },
)
async def query_graph_cypher(args: dict[str, Any]) -> dict[str, Any]:
    """Execute a raw Cypher query against Neo4j (fallback for advanced queries)."""
    cypher_query = args["cypher_query"]

    query_upper = cypher_query.strip().upper()
    forbidden = ["CREATE", "MERGE", "DELETE", "DETACH", "SET ", "REMOVE"]
    if any(kw in query_upper for kw in forbidden):
        return {
            "content": [{"type": "text", "text": "Error: Only read-only queries allowed."}],
            "is_error": True,
        }

    try:
        def _run_query():
            with _neo4j_driver.session(database=_settings.neo4j_database) as session:
                result = session.run(cypher_query)
                return [dict(record) for record in result]

        records = await asyncio.to_thread(_run_query)
        text = json.dumps(records, indent=2, default=str)
        logger.info("query_graph_cypher returned %d records", len(records))
        return {"content": [{"type": "text", "text": text}]}

    except Exception as e:
        logger.error("query_graph_cypher error: %s", e, exc_info=True)
        return {
            "content": [{"type": "text", "text": f"Error: {e}"}],
            "is_error": True,
        }


@tool(
    name="derive_xcallback_url",
    description=(
        "Generate a NotePlan x-callback-url link for a note file. "
        "The link opens the note directly in the NotePlan app."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Relative path to the NotePlan file",
            },
            "heading": {
                "type": "string",
                "description": "Optional heading within the note to link to",
            },
        },
        "required": ["file_path"],
    },
)
async def derive_xcallback_url(args: dict[str, Any]) -> dict[str, Any]:
    """Generate a NotePlan x-callback-url via tidy-mcp service."""
    file_path = args["file_path"]
    heading = args.get("heading")

    try:
        url = f"{_settings.tidy_mcp_url}/tools/derive_xcallback_url_from_noteplan_file"
        payload = {"file_path": file_path}
        if heading:
            payload["heading"] = heading

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("success") and "x_callback_url" in result:
            return {
                "content": [{"type": "text", "text": result["x_callback_url"]}]
            }
        else:
            error_msg = result.get("error", "Unknown error")
            return {
                "content": [
                    {"type": "text", "text": f"Error generating link: {error_msg}"}
                ],
                "is_error": True,
            }

    except Exception as e:
        logger.error("derive_xcallback_url error: %s", e, exc_info=True)
        return {
            "content": [{"type": "text", "text": f"Error: {e}"}],
            "is_error": True,
        }


# ---------------------------------------------------------------------------
# MCP server factory
# ---------------------------------------------------------------------------

# semantic_search is excluded until an embedding provider is configured.
# See task #20: Add Voyage AI embeddings to Claude agent.
ALL_TOOLS = [
    read_note,
    build_knowledge_graph,
    query_knowledge_graph,
    query_graph_cypher,
    derive_xcallback_url,
]

TOOL_NAMES = [
    "mcp__notes__read_note",
    "mcp__notes__build_knowledge_graph",
    "mcp__notes__query_knowledge_graph",
    "mcp__notes__query_graph_cypher",
    "mcp__notes__derive_xcallback_url",
]


def create_notes_mcp_server():
    """Create the in-process MCP server with all note tools."""
    return create_sdk_mcp_server(
        name="notes",
        version="1.0.0",
        tools=ALL_TOOLS,
    )

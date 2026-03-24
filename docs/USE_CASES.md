# Use Cases

A living catalog mapping each feature to its implementing code, tests, and evals.

## UC-1: Natural Language Note Query (Existing)

**What**: Ask questions about your notes, get AI-synthesized answers
**Endpoint**: `POST /api/v1/notes/query` (agentic-api :8001)
**Code**:
- Agent: `src/knowledge_agents/agents/note_query_agent.py`
- Service: `src/knowledge_agents/services/note_query_service.py`
- Prompts: `src/knowledge_agents/prompts/note_query_agent.py`
- Vector search: `src/knowledge_agents/database/queries/query_vector_store.py`
- Guardrails: `src/knowledge_agents/guardrails/input/`, `output/`
**Tests**: `tst/integration/agents/test_note_query_agent.py`

## UC-2: Knowledge Graph Building (Existing)

**What**: Extract entities and relationships from notes into Neo4j
**Entry point**: `scripts/seed_graph_database.py`, `scripts/build_neo4j_graph.py`
**Code**:
- Agent: `src/knowledge_agents/agents/graph_builder_agent.py`
- Graph utils: `src/knowledge_agents/utils/graph_utils.py`
- Neo4j client: `src/knowledge_agents/clients/neo4j_client.py`
- Types: `src/knowledge_agents/types/graph.py`
**Tests**: None yet (tracked gap)

## UC-3: NotePlan File Ingestion (Existing)

**What**: Parse NotePlan markdown files, extract structure, seed DB + vector store
**Entry points**: `scripts/seed_database.py`, `scripts/seed_vector_store.py`
**Code**:
- Parser: `src/knowledge_agents/notes/parser.py`
- Traversal: `src/knowledge_agents/notes/traversal.py`
- Filter: `src/knowledge_agents/notes/filter.py`
- Generators: `src/knowledge_agents/notes/generators.py`
**Tests**: `tst/unit/notes/`

## UC-4: Interactive Claude Agent -- Note Search + Graph Exploration (NEW)

**What**: Multi-turn conversational agent that searches notes, builds graphs, and explores relationships
**Endpoint**: `POST /api/v1/chat` and `POST /api/v1/chat/stream` (claude-agent :8004)
**Code**:
- Agent: `src/knowledge_agents/claude_agent/agent.py`
- Tools: `src/knowledge_agents/claude_agent/tools.py`
- Server: `src/knowledge_agents/claude_agent/server.py`
- Prompts: `src/knowledge_agents/claude_agent/prompts.py`
- Config: `src/knowledge_agents/claude_agent/config.py`
**Tests**: `tst/unit/claude_agent/`, `tst/integration/claude_agent/`
**Evals**: `evals/claude_agent/`

## UC-5: Vector + Graph Combined Query (NEW)

**What**: Use Qdrant to find relevant notes, then Neo4j to explore entity relationships
**How**: Claude agent chains `semantic_search` -> `read_note` -> `build_knowledge_graph` -> `query_knowledge_graph`
**Code**: Orchestrated by Claude agent via tools in `src/knowledge_agents/claude_agent/tools.py`
**Reuses**: `graph_utils.create_graph_nodes_and_relationships()`, `notes.parser.read_noteplan_file()`

## UC-6: Section-Level Note Indexing (NEW)

**What**: Parse NotePlan files into heading-level sections, optionally summarize via local LLM, embed, and store in Qdrant + Neo4j
**Pipeline**: `scripts/seed_sections.py` — 4-phase (parse → summarize → embed → store)
**Code**:
- Types: `src/knowledge_agents/types/section.py`
- Splitting: `src/knowledge_agents/utils/text_splitters.py` (heading paths)
- Summarizer: `src/knowledge_agents/services/summarizer.py`
- Delta tracking: `src/knowledge_agents/utils/delta_tracker.py`
- Graph storage: `src/knowledge_agents/utils/graph_utils.py` (Section nodes)
**Models**: Qwen3.5-35B-A3B (summarization), Qwen3-Embedding-8B (embeddings)
**Docs**: `docs/SECTION_INDEXING_PIPELINE.md`

## UC-7: LLM Observability via Langfuse (NEW)

**What**: Trace every LLM call with input/output/cost/tools, visualize multi-turn agent sessions, track quality over time
**URL**: http://localhost:3210 (admin@localhost.dev / knowledge123)
**Code**:
- Tracing utility: `src/knowledge_agents/utils/langfuse_trace.py`
- Agent instrumentation: `src/knowledge_agents/claude_agent/agent.py`
- Summarizer instrumentation: `src/knowledge_agents/services/summarizer.py`
**Stack**: Langfuse v3 + ClickHouse + Redis + MinIO (shares existing Postgres)
**Docs**: `docs/OBSERVABILITY.md`

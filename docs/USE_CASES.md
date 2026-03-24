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

## UC-2: Knowledge Graph Building (Graphiti-Powered)

**What**: Build temporal knowledge graph from notes using Graphiti — automatic entity extraction, deduplication, temporal tracking, hybrid search
**Entry points**: `build_knowledge_graph` MCP tool, `scripts/seed_sections.py` Phase D, `scripts/spike_graphiti.py`
**Code**:
- Graphiti client: `src/knowledge_agents/claude_agent/graphiti_client.py`
- MCP tools: `src/knowledge_agents/claude_agent/tools.py` (build_knowledge_graph, query_knowledge_graph)
- Spike: `scripts/spike_graphiti.py`
**Models**: Qwen3.5-35B-A3B (extraction), Qwen3-Embedding-8B (embeddings)
**Docs**: `docs/GRAPHITI_INTEGRATION.md`
**Legacy** (deprecated): `graph_builder_agent.py`, `graph_utils.py` — kept for backward compat with old agentic-api

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

## UC-8: Model Configuration Evals (NEW)

**What**: A/B compare LM Studio model configs (temperature, thinking mode, model size) for summarization quality, with scores posted to Langfuse
**Commands**: `make model-eval`, `make model-eval-config CONFIG="9b"`, `make model-eval-report`
**Code**:
- Runner: `evals/model_config/runner.py` (config sweep, calls summarizer directly)
- Scorer: `evals/model_config/scorer.py` (conciseness, non-empty, ROUGE-L, LLM grading)
- Configs: `evals/model_config/configs.py` (5 configs: temperature sweep + thinking + model comparison)
- Dataset: `evals/model_config/datasets/summarization.json` (10 real note sections from Neo4j)
**Results**: Scores in Langfuse (180+ scores), JSON in `evals/model_config/results/`, markdown report
**Outcome**: Qwen3.5-9B selected over 35B-A3B (0.71 vs 0.64 overall, 100% vs 90% non-empty)
**Docs**: `docs/MODEL_DECISIONS.md`

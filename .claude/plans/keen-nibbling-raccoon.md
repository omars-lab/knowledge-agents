# Graphiti Evaluation: Temporal Knowledge Graph for NotePlan Notes

## Context

Our current graph pipeline uses hand-built Neo4j operations: manual entity extraction via Claude Agent, MERGE-by-name deduplication, simple CONTAINS relationships, and substring-based entity linking. This works but lacks temporal tracking, entity resolution, conflict detection, and hybrid search.

[Graphiti](https://github.com/getzep/graphiti) (by Zep) is an open-source temporal knowledge graph engine built on Neo4j that provides automatic entity extraction, temporal fact validity, entity resolution, hybrid search (semantic + keyword + graph traversal), and community detection — all designed for AI agent memory.

**Goal:** Run a spike to evaluate whether Graphiti can replace or augment our graph building pipeline, testing with real NotePlan notes against our existing Neo4j.

## Key Research Findings

| Dimension | Our Pipeline | Graphiti |
|-----------|-------------|----------|
| Entity extraction | Claude Agent (manual prompting) | LLM-powered with structured output |
| Temporal tracking | `last_processed` only | First-class validity windows on every fact |
| Entity resolution | MERGE by name (no dedup) | Automatic name variant resolution |
| Conflict handling | Overwrites silently | Fact invalidation with timestamps |
| Search | Cypher queries only | Hybrid: semantic + keyword + graph traversal |
| Incremental updates | Delta indexing (content hashes) | Episode-based incremental processing |
| Provenance | Note → Entity CONTAINS | Full chain (fact → episode → source) |
| Local LLM | LM Studio (works) | **Yes** — `OpenAIGenericClient(base_url="http://mac-studio.local:1234/v1")` |
| Custom entity types | Entity.type property | Pydantic models per type (Person, Project, etc.) |
| Embeddings | Qdrant (4096 dims, Qwen3) | Pluggable `EmbedderClient` — can wrap our Qdrant |
| NotePlan sections → ? | SectionData nodes | **Episodes** (perfect conceptual match) |

**Sources:**
- [Graphiti GitHub](https://github.com/getzep/graphiti)
- [Graphiti + Neo4j Blog](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/)
- [Graphiti PyPI (v0.28.2)](https://pypi.org/project/graphiti-memory/)
- [Graphiti Overview (Zep Docs)](https://help.getzep.com/graphiti/getting-started/overview)
- [Building AI Knowledge Graph with Graphiti](https://blog.futuresmart.ai/building-ai-knowledge-graph-using-graphiti-and-neo4j)
- [Graphiti LLM Config (Zep Docs)](https://help.getzep.com/graphiti/configuration/llm-configuration)
- [OpenAIGenericClient source](https://github.com/getzep/graphiti/blob/main/graphiti_core/llm_client/openai_generic_client.py)

## Risks

1. **Structured output requirement** — Graphiti needs LLMs that produce valid JSON per schema. Qwen3.5-9B may not reliably do this. If extraction fails, the graph is incomplete.
2. **Neo4j schema conflict** — Graphiti creates its own node types (Entity, Episodic, Community, Saga) and relationships (RELATES_TO, MENTIONS, HAS_MEMBER). Must use a **separate Neo4j database** to avoid conflicting with our existing schema.
3. **Embedding model mismatch** — Graphiti defaults to OpenAI embeddings. We'd need a custom `EmbedderClient` wrapping our Qwen3-Embedding-8B.
4. **NotePlan-specific features lost** — xcallback URLs, heading paths, file type awareness aren't Graphiti concepts. We'd need to preserve these as episode metadata or entity properties.

## Plan

### Step 1: Install Graphiti and set up isolated Neo4j database

Install `graphiti-memory` package. Create a `graphiti` database in our existing Neo4j instance (separate from the `neo4j` database we use now) to avoid schema conflicts.

```bash
conda run -n knowledge-agents pip install graphiti-memory
```

Create database:
```cypher
CREATE DATABASE graphiti IF NOT EXISTS
```

### Step 2: Create a spike script

**New file:** `scripts/spike_graphiti.py`

A standalone script that:
1. Initializes Graphiti with our Neo4j + LM Studio
2. Reads 5-10 NotePlan sections from our existing Neo4j
3. Ingests each section as a Graphiti episode
4. Queries the resulting graph
5. Compares entity extraction quality vs our current pipeline

```python
from graphiti_core import Graphiti
from graphiti_core.llm_client import OpenAIGenericClient, LLMConfig
from graphiti_core.embedder import OpenAIEmbedder, EmbedderConfig

# Point to LM Studio for LLM
llm_client = OpenAIGenericClient(LLMConfig(
    api_key="lm-studio",
    base_url="http://mac-studio.local:1234/v1",
    model="qwen3.5-9b",
))

# Point to LM Studio for embeddings
embedder = OpenAIEmbedder(EmbedderConfig(
    api_key="lm-studio",
    base_url="http://mac-studio.local:1234/v1",
    model="text-embedding-qwen3-embedding-8b",
))

# Initialize with separate database
graphiti = Graphiti(
    "bolt://localhost:7687", "neo4j", "knowledge123",
    llm_client=llm_client,
    embedder=embedder,
)

# Define custom entity types matching our schema
from pydantic import BaseModel

class PersonEntity(BaseModel):
    email: str = ""
    role: str = ""

class ProjectEntity(BaseModel):
    repo: str = ""
    status: str = ""

class ToolEntity(BaseModel):
    homepage: str = ""

entity_types = {
    "Person": PersonEntity,
    "Project": ProjectEntity,
    "Tool": ToolEntity,
}

# Ingest a NotePlan section as an episode
await graphiti.add_episode(
    name="Moving Faster",
    episode_body="* Tokens / Claude Access\n* API Key?...",
    source_description="NotePlan Calendar/20260323.md",
    reference_time=datetime(2026, 3, 23),
    entity_types=entity_types,
)

# Search
results = await graphiti.search("Claude access tokens")
```

### Step 3: Define evaluation criteria

Compare Graphiti output vs our current pipeline on the same 10 sections used in model config evals:

| Dimension | How to measure |
|-----------|---------------|
| **Entity extraction quality** | Count entities found, check for missed/hallucinated ones |
| **Entity resolution** | Does Graphiti merge "AI Agent" and "AI Agents" as one entity? |
| **Relationship richness** | Are relationships more specific than our generic RELATED_TO? |
| **Temporal tracking** | Does it correctly handle facts that change across notes? |
| **Search quality** | Compare `graphiti.search()` vs our Cypher queries for same queries |
| **Structured output reliability** | How often does Qwen3.5-9B produce valid JSON for Graphiti? |
| **Latency** | Time per episode ingestion vs our `build_knowledge_graph` tool |

### Step 4: Run the spike and collect results

Run `scripts/spike_graphiti.py` against the 10 eval sections. Save results as JSON for comparison.

Post results to Langfuse with trace name `graphiti-eval` for visual comparison alongside our existing `model-eval` traces.

### Step 5: Document findings

Write up results in `docs/TECH_DESIGN.md` under a new "Graphiti Evaluation" section:
- What worked well
- What didn't (structured output failures, missing features)
- Recommendation: adopt, augment, or skip
- If adopting: migration plan for replacing graph_utils.py

## Critical Files

| File | Action |
|------|--------|
| `scripts/spike_graphiti.py` | New: evaluation spike script |
| `docs/TECH_DESIGN.md` | Update with findings |
| `docs/MODEL_DECISIONS.md` | If switching graph approach, record decision |

## Verification

1. `pip install graphiti-memory` succeeds
2. `spike_graphiti.py` ingests 10 sections without crashing
3. Entities appear in Neo4j `graphiti` database
4. Search returns relevant results
5. Comparison table shows measurable differences vs current pipeline
6. Results logged in Langfuse

## Decision Criteria

**Adopt Graphiti if:**
- Structured output works reliably with Qwen3.5-9B (>90% valid JSON)
- Entity resolution catches duplicates our pipeline misses
- Temporal tracking adds value for note evolution
- Search quality is meaningfully better

**Keep current pipeline if:**
- Structured output fails frequently with local LLMs
- Graphiti's schema is too rigid for our NotePlan-specific features
- The overhead of maintaining two graph approaches isn't worth it
- Performance is significantly worse (>3x slower per episode)

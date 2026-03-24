# Graphiti Integration Plan

> **Living Document** — update as integration progresses.

## What is Graphiti?

[Graphiti](https://github.com/getzep/graphiti) (by Zep) is an open-source temporal knowledge graph engine built on Neo4j. Unlike static knowledge graphs, Graphiti tracks **when facts became true and when they were superseded**, enabling point-in-time queries and historical analysis.

## Why Graphiti?

### Problems with Our Current Pipeline

| Problem | Current State | Impact |
|---------|--------------|--------|
| **No temporal tracking** | `last_processed` timestamp only | Can't answer "what changed since last week?" |
| **No entity resolution** | MERGE by name (exact match only) | "AI Agent" and "AI Agents" are two entities |
| **No conflict detection** | Overwrites silently | If a fact changes, old version is lost |
| **Search is limited** | Cypher queries only | No semantic + graph hybrid search |
| **Manual entity extraction** | Claude Agent extracts via prompt | Inconsistent, depends on prompt quality |
| **No provenance** | Note → Entity CONTAINS | Can't trace a fact back to its source sentence |
| **Weak relationship typing** | Most edges are RELATED_TO | Loses the richness of temporal facts |

### What Graphiti Adds

| Capability | How It Works | Use Case |
|-----------|-------------|----------|
| **Temporal facts** | Every edge has `valid_at`, `invalid_at`, `expired_at` | "When did I start using Neo4j?" → traces back to the exact note and date |
| **Entity resolution** | LLM-powered deduplication during ingestion | "Claude", "Claude AI", "Anthropic Claude" → merged into one entity |
| **Conflict detection** | New facts automatically invalidate contradicting old facts | If a project status changes from "active" to "completed", the old fact is marked `expired_at` |
| **Hybrid search** | Semantic (embedding) + keyword (full-text) + graph traversal | "What's connected to my AI projects?" → combines vector similarity with graph hops |
| **Community detection** | Automatic clustering of related entities | Discover topic clusters across notes you didn't know were related |
| **Episode provenance** | Every entity/edge traces back to source episodes | Click on an entity → see every note section that mentioned it |
| **Automatic extraction** | LLM extracts entities + relationships from raw text | No manual prompt engineering — Graphiti handles extraction prompts internally |

### Use Cases This Enables

#### 1. Temporal Knowledge Queries
```
"What projects was I working on in January 2026?"
"When did I first mention ServiceNow in my notes?"
"How has my understanding of knowledge graphs evolved over time?"
```
Graphiti's temporal edges let you reconstruct your knowledge state at any point in time.

#### 2. Cross-Note Discovery
```
"What connects my AI work to my personal projects?"
"Which people appear in both my work and personal notes?"
```
Community detection reveals clusters and bridges you didn't explicitly create.

#### 3. Contradiction Detection
```
"I thought the deadline was March 15 — when did it change?"
```
When a new note contradicts an old fact, Graphiti marks the old edge as expired and creates a new one with the updated fact.

#### 4. Source Tracing
```
"Where did I first learn about Qwen3.5?"
```
Every entity traces back through episodes to the exact note section where it was first mentioned.

#### 5. Rich Relationship Understanding
```
"What does Omar WORK_ON vs what does he MENTION?"
```
Instead of generic RELATED_TO, Graphiti extracts specific relationship types with natural language fact descriptions.

#### 6. Knowledge Graph Evolution
```
"Show me how my graph grew over the last month"
```
Temporal metadata enables visualizing graph growth over time — see which topics expanded, which faded.

## Spike Results

**5/5 episodes ingested successfully** with local LLMs:

| Metric | Value |
|--------|-------|
| Episodes ingested | 5/5 (100%) |
| Entity nodes | 87 |
| RELATES_TO edges (temporal) | 57 |
| MENTIONS edges (provenance) | 89 |
| Hybrid search results | 5 hits |
| Avg latency per episode | 193s |

**Models used:**
- **Extraction:** Qwen3.5-35B-A3B (needs structured JSON output — 9B fails)
- **Embeddings:** Qwen3-Embedding-8B (4096 dims, MTEB #1)
- **All local** — no API costs

**Key technical solutions:**
1. Custom `LMStudioClient` that injects JSON schema into prompts (bypasses `response_format` which conflicts with thinking mode)
2. JSON extraction with retry + error feedback (2 attempts per call)
3. `group_id` partitioning to isolate Graphiti data from our existing schema
4. Cleaned old Entity nodes to resolve UNIQUE constraint conflicts

## Integration Plan

### Phase 1: Core Integration (Steps 2-4)

Create `graphiti_client.py` module, replace `build_knowledge_graph` and `query_knowledge_graph` tools.

**Files:**
- `src/knowledge_agents/claude_agent/graphiti_client.py` — init Graphiti with LM Studio
- `src/knowledge_agents/claude_agent/tools.py` — simplify tools to use Graphiti
- `src/knowledge_agents/claude_agent/prompts.py` — update for Graphiti-aware agent

**Before:** Agent manually extracts entities → `create_graph_nodes_and_relationships()`
**After:** Agent passes note content → `graphiti.add_episode()` → automatic extraction

### Phase 2: Pipeline Integration (Step 5)

Replace section indexing Phase D with Graphiti episodes.

**File:** `scripts/seed_sections.py`

Each section becomes a Graphiti episode with:
- `name` = section heading
- `episode_body` = section raw text
- `source_description` = NotePlan file path + heading path
- `reference_time` = file modification time
- `group_id` = "noteplan"

### Phase 3: Search + Rendering (Steps 6-7)

Update SVG renderer and agent search to use Graphiti's graph.

**Files:**
- `scripts/render_graph.py` — query Graphiti entities + RELATES_TO edges
- Agent tools — use `graphiti.search()` for hybrid search

### Phase 4: Cleanup + Docs (Steps 8-10)

Remove deprecated graph_utils functions, update GRAPH_SCHEMA.md for Graphiti's schema, update all living docs.

## Architecture After Integration

```
NotePlan Files
     │
     ▼
[Parse + Split into Sections]
     │
     ├──▶ [Summarize (Qwen3.5-9B)]  → Qdrant (sections_collection)
     │
     └──▶ [Graphiti Episode Ingestion (Qwen3.5-35B-A3B)]
              │
              ├── Entity extraction (automatic)
              ├── Relationship extraction (temporal)
              ├── Entity resolution (dedup)
              ├── Embeddings (Qwen3-8B)
              └── Neo4j storage
                   ├── Entity nodes (with group_id)
                   ├── Episodic nodes (provenance)
                   ├── RELATES_TO edges (temporal facts)
                   ├── MENTIONS edges (episode → entity)
                   └── Community nodes (auto-clustering)
```

**Two parallel storage paths:**
1. **Qdrant** — section-level embeddings for semantic search (fast, vector-only)
2. **Neo4j via Graphiti** — temporal knowledge graph for entity/relationship queries (rich, graph-aware)

## Model Strategy

| Role | Model | Why |
|------|-------|-----|
| **Summarization** | Qwen3.5-9B | Best eval score (0.71), 100% non-empty, concise |
| **Extraction (Graphiti)** | Qwen3.5-35B-A3B | Reliable structured JSON output (9B fails with routing bug) |
| **Embeddings** | Qwen3-Embedding-8B | MTEB #1 (70.58), 4096 dims |

All three can be loaded simultaneously on Mac Studio (96GB):
- 35B-A3B: 22 GB
- 9B: 6.5 GB
- Embedding-8B: 4.7 GB
- **Total: 33.2 GB** (35% of 96GB)

## Gotchas Discovered During Spike

1. **`response_format: json_schema` + Qwen3.5 thinking mode = empty content.** Must inject schema into system prompt instead and let model think naturally.

2. **Qwen3.5-9B can't do structured JSON output.** Routes all output to `reasoning_content` with empty `content`. Use 35B-A3B for extraction.

3. **Neo4j Community Edition = single database.** Graphiti shares the `neo4j` database with our existing data. Use `group_id` to partition.

4. **Old Entity nodes cause UNIQUE constraint conflicts.** Must clean entities without `group_id` before Graphiti can create new ones with the same names.

5. **Graphiti uses many LLM + embedding calls per episode** (~10-20 calls). Average 193s per episode on local hardware. Batch processing is slow but free.

6. **Custom `LMStudioClient` needed.** Override `_generate_response` to: skip `response_format`, inject schema into prompt, extract JSON from content, validate with Pydantic, retry with error feedback.

## Sources

- [Graphiti GitHub](https://github.com/getzep/graphiti)
- [Graphiti + Neo4j Blog](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/)
- [Graphiti PyPI (v0.28.2)](https://pypi.org/project/graphiti-memory/)
- [Graphiti Overview (Zep Docs)](https://help.getzep.com/graphiti/getting-started/overview)
- [Graphiti LLM Config](https://help.getzep.com/graphiti/configuration/llm-configuration)
- [OpenAIGenericClient source](https://github.com/getzep/graphiti/blob/main/graphiti_core/llm_client/openai_generic_client.py)
- [Building AI Knowledge Graph with Graphiti](https://blog.futuresmart.ai/building-ai-knowledge-graph-using-graphiti-and-neo4j)

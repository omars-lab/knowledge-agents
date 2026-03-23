# Graph Schema, Link Resolution, and Living Documentation

## Context

The knowledge graph has a minimal working schema (Note, Entity, typed relationships) but several gaps:
- **No link metadata on nodes** — xcallback URLs are computed on-demand via HTTP, not stored
- **Entity `properties` field exists but is never populated** — the tool schema doesn't expose it, the prompt doesn't ask for it
- **No `url` field** — entities have no way to link to external resources
- **Node types not documented** — schema lives in scattered code, prompts, and skills with minor inconsistencies
- **No living doc** cataloging the graph schema, node types, edge types, and link resolution rules

**Goal:** Define a complete graph schema with link-resolving metadata per node type, implement a `LinkResolver`, store link metadata on nodes at graph-build time, and create a living doc that catalogs everything.

## Plan

### Step 1: Create `docs/GRAPH_SCHEMA.md` — the living reference

**File:** `docs/GRAPH_SCHEMA.md`

A comprehensive, authoritative reference for the knowledge graph schema. Add to the "Living Documents" list in CLAUDE.md.

Contents:
- **Node types** — every label, its purpose, required/optional properties, and link template
- **Relationship types** — every edge type, its semantics, valid source→target pairs
- **Link resolution rules** — how each node type generates a clickable URL
- **Property conventions** — what metadata the agent should extract per entity type
- **Color coding** — visual identity per type (matches renderer)

#### Node Type Catalog

| Label | Purpose | Required Properties | Link-Resolving Properties | URL Template |
|-------|---------|--------------------|--------------------------|-|
| `Note` | A NotePlan file | `file_path`, `last_processed` | `file_path` | `noteplan://x-callback-url/openNote?filename={url_encode(relative_path)}` |
| `Person` | A named person | `name`, `type=Person` | `email`, `url` | `mailto:{email}` or `{url}` if provided |
| `Project` | A project/initiative | `name`, `type=Project` | `url`, `repo` | `{url}` or `https://github.com/{repo}` |
| `Topic` | A subject area | `name`, `type=Topic` | — | No external link (internal concept) |
| `Concept` | An idea/framework | `name`, `type=Concept` | `url` | `{url}` if provided |
| `Organization` | A company/team | `name`, `type=Organization` | `url` | `{url}` if provided |
| `Tool` | Software/service | `name`, `type=Tool` | `url` | `{url}` if provided |
| `Location` | A place | `name`, `type=Location` | `url` | `{url}` or Google Maps link |
| `Event` | A named event | `name`, `type=Event` | `date`, `url` | `{url}` if provided |
| `Date` | A specific date | `name`, `type=Date` | `date` | `noteplan://x-callback-url/openNote?noteDate={YYYYMMDD}` |
| `Task` | An action item | `name`, `type=Task` | `note_file_path`, `status` | Link to containing Note |

#### Relationship Catalog

| Type | Semantics | Valid Source → Target | Properties |
|------|-----------|----------------------|------------|
| `CONTAINS` | Note has this entity | Note → Entity | — |
| `RELATED_TO` | General connection | Entity → Entity | `context` |
| `WORKS_ON` | Person involved in project | Person → Project | `role` |
| `MENTIONS` | Direct reference | Entity → Entity | — |
| `REFERENCES` | Conceptual reference | Entity → Entity | — |
| `OCCURS_AT` | Event at time/place | Event → Date/Location | — |
| `BELONGS_TO` | Membership | Entity → Organization | `role` |
| `PART_OF` | Hierarchical containment | Entity → Entity | — |

### Step 2: Create `src/knowledge_agents/claude_agent/link_resolver.py`

**File:** `src/knowledge_agents/claude_agent/link_resolver.py`

A schema-driven link resolver that reads node properties and returns the appropriate URL.

```python
def resolve_link(node_type: str, properties: dict) -> str | None:
    """Resolve a clickable URL for a graph node based on its type and properties."""
```

Resolution logic (in priority order per type):
1. If the node has a `url` property → return it directly
2. If `Note` → derive noteplan:// URL from `file_path` (via tidy-mcp or local logic)
3. If `Date` → derive noteplan calendar link: `noteplan://x-callback-url/openNote?noteDate={YYYYMMDD}`
4. If `Person` with `email` → `mailto:{email}`
5. If `Project` with `repo` → `https://github.com/{repo}`
6. If `Task` with `note_file_path` → derive noteplan link for containing note
7. Otherwise → `None` (no link)

Also expose:
```python
NODE_SCHEMA: dict[str, NodeTypeConfig]  # type → required props, optional props, link template, color
```

### Step 3: Update `build_knowledge_graph` tool to accept and store link metadata

**File:** `src/knowledge_agents/claude_agent/tools.py`

Expand the tool's `input_schema` to include optional `properties` on entities:

```json
"entities": [{
    "name": "string",
    "type": "string",
    "url": "string (optional — external URL for this entity)",
    "properties": {"type": "object", "description": "Additional metadata (email, repo, date, etc.)"}
}]
```

The agent prompt already says to extract properties — now the schema actually accepts them.

### Step 4: Update agent system prompt to extract link metadata

**File:** `src/knowledge_agents/claude_agent/prompts.py`

Add guidance on what properties to extract per entity type:

```
When extracting entities, include relevant metadata:
- Person: email, role, url (LinkedIn/website)
- Project: repo (GitHub slug), url
- Tool: url (homepage)
- Organization: url (website)
- Event: date (YYYY-MM-DD), url
- Date: date (YYYY-MM-DD)
- Task: status (done/pending), note_file_path
```

### Step 5: Update renderer to use LinkResolver

**File:** `scripts/render_graph.py`

Replace the inline `_get_xcallback_url()` with `LinkResolver`:
- Query Neo4j for full node properties (not just name/type)
- Pass properties to `resolve_link()`
- Embed URLs in SVG nodes

Update the Cypher queries to return node properties needed for link resolution.

### Step 6: Store xcallback URL on Note nodes at build time

**File:** `src/knowledge_agents/claude_agent/tools.py`

When `build_knowledge_graph` creates/updates a Note node, also resolve and store the xcallback URL:
```python
# After MERGE (n:Note {file_path: $file_path})
# SET n.xcallback_url = <resolved URL>
```

This way the URL is computed once and persisted — no HTTP calls at render time.

### Step 7: Update graph_utils.py to store properties on entities

**File:** `src/knowledge_agents/utils/graph_utils.py`

The `create_graph_nodes_and_relationships` function already does `e += $properties` on entity nodes. Ensure the `url` and other link-relevant properties flow through from the tool input to Neo4j storage.

### Step 8: Update living docs

**Files:**
- `CLAUDE.md` — Add `docs/GRAPH_SCHEMA.md` to Living Documents list
- `docs/USE_CASES.md` — Add UC-6: Graph Schema & Link Resolution
- `docs/GRAPH_SCHEMA.md` — The new living doc (from Step 1)
- `.claude/skills/knowledge-index.md` — Update schema section to reference `docs/GRAPH_SCHEMA.md`

### Step 9: Update unit tests

**Files:** `tst/unit/claude_agent/test_tools.py`

- Test that `build_knowledge_graph` accepts entities with `url` and `properties`
- Test `link_resolver.py` — resolve_link for each node type
- Test that Note nodes get `xcallback_url` stored

## Critical Files

| File | Change |
|------|--------|
| `docs/GRAPH_SCHEMA.md` | New: living reference for graph schema |
| `src/knowledge_agents/claude_agent/link_resolver.py` | New: schema-driven link resolution |
| `src/knowledge_agents/claude_agent/tools.py` | Expand entity schema, store xcallback on Notes |
| `src/knowledge_agents/claude_agent/prompts.py` | Guide agent to extract link metadata |
| `scripts/render_graph.py` | Use LinkResolver instead of inline tidy-mcp calls |
| `src/knowledge_agents/utils/graph_utils.py` | Ensure properties flow to Neo4j |
| `CLAUDE.md` | Add GRAPH_SCHEMA.md to living docs |
| `docs/USE_CASES.md` | Add UC-6 |
| `.claude/skills/knowledge-index.md` | Reference GRAPH_SCHEMA.md |
| `tst/unit/claude_agent/test_tools.py` | Test expanded schema + link resolver |

## Verification

1. Unit tests pass: `make claude-agent-test`
2. Build a graph with properties: call the agent to read a note and build graph — verify entities have `url` stored in Neo4j
3. Render SVG: `make claude-agent-graph` — verify Note nodes have clickable noteplan:// links, entities with URLs are also clickable
4. Query Neo4j: `MATCH (e:Entity) WHERE e.url IS NOT NULL RETURN e.name, e.url` — verify URLs persisted
5. Check living doc: `docs/GRAPH_SCHEMA.md` matches what's actually in the code

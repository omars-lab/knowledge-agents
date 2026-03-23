# Knowledge Graph Schema

> **Living Document** — update when adding node types, relationship types, or link resolution rules.
> Referenced by: `knowledge-index.md` skill, `render_graph.py`, `link_resolver.py`, `tools.py`

## Node Types

### Note

A NotePlan file indexed into the graph.

| Property | Required | Description |
|----------|----------|-------------|
| `file_path` | Yes | Relative path from NotePlan root (e.g., `Calendar/20251218.md`) |
| `file_name` | No | Filename without path |
| `last_processed` | No | ISO timestamp of last indexing |
| `git_hash` | No | Git hash when file was last indexed (for delta detection) |
| `xcallback_url` | No | Pre-resolved `noteplan://` link (stored at build time) |
| `file_type` | No | `calendar` or `note` |

**Link:** `noteplan://x-callback-url/openNote?filename={url_encode(relative_path)}`
**Color:** `#FFF3CD` (cream/gold)
**Shape:** `note` (folded corner)
**Constraint:** UNIQUE(`file_path`)

### Entity Types

All entities share the `Entity` label in Neo4j with a `type` property distinguishing them.

#### Person

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Full name |
| `type` | Yes | `Person` |
| `email` | No | Email address |
| `url` | No | Website or LinkedIn profile |
| `role` | No | Job title or role |

**Link priority:** `url` > `mailto:{email}` > none
**Color:** `#4A90D9` (blue)

#### Project

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Project name |
| `type` | Yes | `Project` |
| `url` | No | Project URL |
| `repo` | No | GitHub slug (e.g., `owner/repo`) |
| `status` | No | `active`, `completed`, `planned` |

**Link priority:** `url` > `https://github.com/{repo}` > none
**Color:** `#50C878` (green)

#### Topic

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Subject area (e.g., "Machine Learning", "Fitness") |
| `type` | Yes | `Topic` |

**Link:** None (internal concept)
**Color:** `#FFB347` (orange)

#### Concept

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Idea or framework name |
| `type` | Yes | `Concept` |
| `url` | No | Reference URL (article, paper) |

**Link priority:** `url` > none
**Color:** `#DDA0DD` (plum)

#### Organization

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Company, team, or institution |
| `type` | Yes | `Organization` |
| `url` | No | Website |

**Link priority:** `url` > none
**Color:** `#FF6B6B` (red)

#### Tool

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Software, service, or library name |
| `type` | Yes | `Tool` |
| `url` | No | Homepage or docs URL |

**Link priority:** `url` > none
**Color:** `#98D8C8` (teal)

#### Location

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Place name |
| `type` | Yes | `Location` |
| `url` | No | Google Maps or website URL |
| `address` | No | Street address |

**Link priority:** `url` > `https://maps.google.com/?q={url_encode(name)}` > none
**Color:** `#F0E68C` (khaki)

#### Event

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Event name |
| `type` | Yes | `Event` |
| `date` | No | ISO date (YYYY-MM-DD) |
| `url` | No | Event page URL |

**Link priority:** `url` > none
**Color:** `#C9B1FF` (light purple)

#### Date

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Date string (e.g., "2025-12-18") |
| `type` | Yes | `Date` |
| `date` | No | ISO date (YYYY-MM-DD) for structured queries |

**Link:** `noteplan://x-callback-url/openNote?noteDate={YYYYMMDD}` (opens calendar day in NotePlan)
**Color:** `#87CEEB` (sky blue)

#### Task

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Task description |
| `type` | Yes | `Task` |
| `status` | No | `done`, `pending`, `cancelled` |
| `note_file_path` | No | File path of the note containing this task |

**Link:** Derive from `note_file_path` using Note link template
**Color:** `#FFD6D6` (light red)

## Relationship Types

| Type | Semantics | Valid Source | Valid Target | Properties |
|------|-----------|-------------|--------------|------------|
| `CONTAINS` | Note mentions this entity | Note | Entity (any) | — |
| `RELATED_TO` | General connection | Entity | Entity | `context` |
| `WORKS_ON` | Person involved in project | Person | Project | `role` |
| `MENTIONS` | Direct reference | Entity | Entity | — |
| `REFERENCES` | Conceptual reference | Entity | Entity | — |
| `OCCURS_AT` | Event at time/place | Event | Date, Location | — |
| `BELONGS_TO` | Membership/affiliation | Person, Project | Organization | `role` |
| `PART_OF` | Hierarchical containment | Entity | Entity | — |

## Link Resolution Rules

Links are resolved by `src/knowledge_agents/claude_agent/link_resolver.py` using this priority:

1. **Explicit `url` property** — if the node has a `url` property, use it directly
2. **Type-specific template** — apply the URL template for the node type (see tables above)
3. **Fallback** — return `None` (node is not clickable)

For `Note` nodes, the `xcallback_url` property is pre-resolved at graph-build time via tidy-mcp and stored on the node. The renderer reads this property directly — no HTTP call needed.

## Property Extraction Guidelines

When the agent extracts entities from notes, it should include link-resolving metadata:

| Entity Type | Extract These Properties |
|-------------|------------------------|
| Person | `email` (if mentioned), `url` (LinkedIn/website), `role` |
| Project | `repo` (GitHub slug), `url` (project page) |
| Tool | `url` (homepage or docs) |
| Organization | `url` (website) |
| Event | `date` (YYYY-MM-DD), `url` (event page) |
| Date | `date` (YYYY-MM-DD) |
| Task | `status` (done/pending), `note_file_path` |
| Topic, Concept, Location | `url` if explicitly referenced in the note |

## Neo4j Constraints and Indexes

```cypher
-- Constraints
CREATE CONSTRAINT note_file_path IF NOT EXISTS FOR (n:Note) REQUIRE n.file_path IS UNIQUE;
CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE;

-- Indexes
CREATE INDEX note_last_processed IF NOT EXISTS FOR (n:Note) ON (n.last_processed);
CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type);
```

## Visual Identity

Used by `scripts/render_graph.py` for SVG rendering:

| Node Type | Color | Shape |
|-----------|-------|-------|
| Note | `#FFF3CD` cream/gold | `note` (folded corner) |
| Person | `#4A90D9` blue | `box` (rounded) |
| Project | `#50C878` green | `box` (rounded) |
| Topic | `#FFB347` orange | `box` (rounded) |
| Concept | `#DDA0DD` plum | `box` (rounded) |
| Organization | `#FF6B6B` red | `box` (rounded) |
| Tool | `#98D8C8` teal | `box` (rounded) |
| Location | `#F0E68C` khaki | `box` (rounded) |
| Event | `#C9B1FF` light purple | `box` (rounded) |
| Date | `#87CEEB` sky blue | `box` (rounded) |
| Task | `#FFD6D6` light red | `box` (rounded) |

# Plan: Rich Card Types + Structured SSE Events

## Problem

The backend has rich structured data (graph nodes with colors/shapes, xcallback URLs, similarity scores, entity metadata) but flattens everything to plain text strings before streaming. The frontend receives only text and renders it as markdown. The pipe between backend and frontend is too narrow.

### Current State

**Backend tools return:** `{"content": [{"type": "text", "text": "..."}]}` — all stringified.

**SSE events emitted:** `tool_start`, `tool_input`, `tool_complete` (input only, no output), `text`, `result`, `error`.

**Frontend renders:** Markdown text, tool pills (name + spinner/checkmark), metadata line.

### What's Available But Not Exposed

| Source | Structured Data Available | Currently Sent As |
|--------|--------------------------|-------------------|
| `semantic_search` | file_path, similarity_score, modified_at, file_size | JSON string in text |
| `read_note` | file content, file_path | Raw markdown text |
| `query_knowledge_graph` | Graphiti entities, relationships, episodes, scores | Formatted markdown |
| `query_graph_cypher` | Neo4j records (nodes, edges, properties, types) | JSON string in text |
| `derive_xcallback_url` | URL, entity type | Plain URL string |
| `link_resolver.py` | 11 entity types with colors, shapes, link templates | Not exposed at all |
| `knowledge_changelog` | Temporal facts, entities, relationships | Markdown sections |

## Architecture: Dual-Channel Tool Returns

Tools need to return **two things**:
1. **Text summary** — for the agent to reason with (existing behavior)
2. **Structured payload** — for the frontend to render rich cards

The structured payload piggybacks on the existing `tool_complete` SSE event:

```json
{
  "type": "tool_complete",
  "name": "semantic_search",
  "input": "{...}",
  "output_text": "Found 5 notes matching 'goals'...",
  "structured": {
    "card_type": "note_cards",
    "data": [
      {
        "file_path": "Notes/Goals.md",
        "title": "Goals",
        "preview": "My 2026 goals include...",
        "xcallback_url": "noteplan://x-callback-url/openNote?filename=Goals.md",
        "similarity_score": 0.92,
        "modified_at": "2026-03-20T10:30:00Z"
      }
    ]
  },
  "duration_ms": 2300,
  "model": "claude-sonnet-4-20250514"
}
```

The `structured` field is optional — tools that don't have rich data omit it and the frontend falls back to the text rendering (current behavior). This is backwards-compatible: the existing `text` events still carry the full agent response.

## Card Types

### 1. Note Cards (`card_type: "note_cards"`)

**Source tools:** `semantic_search`, `read_note`

Notes are classified by `note_type` which determines the card's visual treatment. Classification is based on file path patterns from the NotePlan directory structure:

| `note_type` | File Path Pattern | Icon | Accent Color | Card Extras |
|-------------|-------------------|------|-------------|-------------|
| `daily` | `Calendar/YYYYMMDD.md` | calendar | `#38bdf8` (blue) | Date header, day-of-week, task completion count |
| `weekly` | `Calendar/YYYY-Wnn.md` | calendar-week | `#818cf8` (indigo) | Week range (Mon-Sun), task summary |
| `plan` | `Notes/**/Plan*.md`, frontmatter `type: plan` | target | `#f59e0b` (amber) | Progress bar (tasks done/total), status badge |
| `template` | `Templates/**/*.md` | template | `#a78bfa` (purple) | "Template" badge, no modified date |
| `project` | `Notes/**/Project*.md`, frontmatter `type: project` | folder | `#50C878` (green) | Status badge (active/complete/paused) |
| `quip` | Quip URL in frontmatter or content | quip-doc | `#F2A93B` (quip orange) | Quip title, "Open in Quip" button, last edited by |
| `file` | Any local file path referenced by agent | file-code | `#64748b` (slate) | File path breadcrumb, "Open in VS Code" button, language badge |
| `note` | Everything else in `Notes/` | note | `#64748b` (slate) | Folder breadcrumb, tag pills |

**Card wireframes by type:**

```
Daily Note:
+------------------------------------------------------------------+
| [cal] Tuesday, March 25, 2026              Calendar/20260325.md  |
|                                                                   |
| Morning meeting with team about Q2 goals.                        |
| Reviewed knowledge-agents progress...          [3/5 tasks done]  |
|                                                                   |
| [Open in NotePlan]                                               |
+------------------------------------------------------------------+

Plan:
+------------------------------------------------------------------+
| [target] Chat UI Implementation Plan     92% match    [Active]   |
|                                                                   |
| Phase 1: Core chat + streaming. Phase 2: Rich                    |
| rendering. Phase 3: Pipeline management...                        |
|                                                                   |
| [██████████░░] 8/12 tasks     [Open in NotePlan]                 |
+------------------------------------------------------------------+

Template:
+------------------------------------------------------------------+
| [tmpl] Weekly Review Template              [Template]             |
|                                                                   |
| # What went well? # What didn't? # Action items                  |
| for next week...                                                  |
|                                                                   |
| [Open in NotePlan]                                               |
+------------------------------------------------------------------+

Quip Document:
+------------------------------------------------------------------+
| [quip] Q2 OKRs - Engineering Team                   [Quip Doc]   |
|                                                                   |
| Objective 1: Ship knowledge-agents v2. KR1: Chat UI              |
| deployed. KR2: 95% uptime. KR3: <2s p99 latency...              |
|                                                                   |
| [Open in Quip]                  Last edited by: Omar, 2d ago     |
+------------------------------------------------------------------+

File Path (code/config):
+------------------------------------------------------------------+
| [</>] src/knowledge_agents/claude_agent/server.py        [Python]|
|                                                                   |
| FastAPI server for the Claude Agent service.                      |
| Endpoints: health, chat, stream, sessions...                      |
|                                                                   |
| [Open in VS Code]              367 lines                         |
+------------------------------------------------------------------+

Regular Note:
+------------------------------------------------------------------+
| [note] Goals                     Notes/ > Goals.md    92% match  |
|                                                                   |
| My 2026 goals include shipping the knowledge-agents              |
| chat UI, completing the graph pipeline, and...                    |
|                                                                   |
| [Open in NotePlan]              Modified: Mar 20, 2026           |
+------------------------------------------------------------------+
```

**SSE payload:**
```json
{
  "card_type": "note_cards",
  "data": [{
    "file_path": "Notes/Goals.md",
    "title": "Goals",
    "note_type": "note",
    "preview": "My 2026 goals include...",
    "xcallback_url": "noteplan://x-callback-url/openNote?filename=Goals.md",
    "similarity_score": 0.92,
    "modified_at": "2026-03-20T10:30:00Z",
    "folder": "Notes",
    "tags": ["goals", "2026"],
    "task_stats": null
  },
  {
    "file_path": "Calendar/20260325.md",
    "title": "Tuesday, March 25, 2026",
    "note_type": "daily",
    "preview": "Morning meeting with team about Q2 goals...",
    "xcallback_url": "noteplan://x-callback-url/openNote?noteDate=20260325",
    "similarity_score": 0.88,
    "modified_at": "2026-03-25T10:30:00Z",
    "folder": "Calendar",
    "tags": [],
    "task_stats": {"done": 3, "total": 5}
  }]
}
```

**`note_type` classification logic** (in tools.py or a new `note_classifier.py`):
```python
def classify_note(file_path: str, content: str = "", frontmatter: dict | None = None) -> str:
    """Classify a note by type based on path, frontmatter, and content."""
    # Calendar types (path-based)
    if re.match(r"Calendar/\d{8}\.md$", file_path):
        return "daily"
    if re.match(r"Calendar/\d{4}-W\d{2}\.md$", file_path):
        return "weekly"
    # Template (path-based)
    if file_path.startswith("Templates/"):
        return "template"
    # Quip doc (frontmatter or content contains quip URL)
    quip_url = None
    if frontmatter and frontmatter.get("quip_url"):
        quip_url = frontmatter["quip_url"]
    elif re.search(r"https://[a-z-]+\.quip\.com/\w+", content):
        quip_url = re.search(r"https://[a-z-]+\.quip\.com/\w+", content).group()
    if quip_url:
        return "quip"
    # Frontmatter explicit type
    if frontmatter and frontmatter.get("type") in ("plan", "project"):
        return frontmatter["type"]
    # Name-based heuristics
    if re.search(r"Plan", Path(file_path).stem, re.IGNORECASE):
        return "plan"
    if re.search(r"Project", Path(file_path).stem, re.IGNORECASE):
        return "project"
    return "note"


def classify_file_path(file_path: str) -> dict | None:
    """Classify a raw file path (code, config, etc.) for a file card.
    Returns None if the path is a NotePlan note (handled by classify_note)."""
    ext = Path(file_path).suffix.lower()
    language_map = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".html": "HTML", ".css": "CSS", ".yml": "YAML", ".yaml": "YAML",
        ".json": "JSON", ".md": "Markdown", ".sh": "Shell",
        ".sql": "SQL", ".toml": "TOML", ".conf": "Config",
        ".dockerfile": "Docker", ".xml": "XML",
    }
    if file_path.startswith(("Notes/", "Calendar/", "Templates/")):
        return None  # NotePlan note — use classify_note instead
    return {
        "note_type": "file",
        "language": language_map.get(ext, ext.lstrip(".").upper() if ext else "File"),
        "vscode_url": f"vscode://file/{file_path}",
    }
```

**Open in VS Code** uses the `vscode://file/{absolute_path}` URI scheme which opens the file in VS Code on desktop. On the Mac Studio, paths are resolved from the repo root. The button should show a code icon and "Open in VS Code" label.

**Quip integration notes:**
- Quip docs can be linked from NotePlan notes via frontmatter (`quip_url: https://company.quip.com/abc123`) or inline URLs
- The "Open in Quip" button links to the Quip URL directly (opens in browser)
- Future: Quip API integration to fetch title, last editor, preview text — for now, extract from the note content that references the Quip doc
- Quip URLs follow the pattern `https://{team}.quip.com/{doc_id}[/{slug}]`

**`task_stats` extraction** (for daily notes and plans):
- Count lines matching `- [x]` (done) and `- [ ]` (open) in the note content
- Return `{"done": N, "total": M}` or `null` if no tasks

**Frontend rendering:**
- Card border-left colored by `note_type` accent color
- Icon in top-left corner by type
- Similarity badge (color gradient red->green) when `similarity_score` present
- "Open in NotePlan" button using xcallback:// URL (app icon, not browser icon)
- Task progress bar for daily/plan types when `task_stats` present
- Folder breadcrumb for regular notes
- Cards stack vertically, full-width on mobile

### 2. Knowledge Graph (`card_type: "graph"`)

**Source tools:** `query_knowledge_graph`, `query_graph_cypher`

```
+------------------------------------------------------------------+
| Knowledge Graph: "goals" connections           23 nodes, 31 edges|
|                                                                   |
|              [Goals] ---HAS_GOAL---> [Ship Chat UI]               |
|                |                          |                       |
|           RELATES_TO              DEPENDS_ON                      |
|                v                          v                       |
|          [2026 Plans]            [Knowledge Agents]               |
|                                                                   |
| [Mermaid] [Force Graph]                          [Fullscreen]    |
+------------------------------------------------------------------+
```

**SSE payload:**
```json
{
  "card_type": "graph",
  "data": {
    "nodes": [
      {"id": "1", "name": "Goals", "type": "Topic", "color": "#9B59B6", "shape": "ellipse", "properties": {}},
      {"id": "2", "name": "Ship Chat UI", "type": "Task", "color": "#E67E22", "shape": "box"}
    ],
    "edges": [
      {"source": "1", "target": "2", "type": "HAS_GOAL", "label": "HAS_GOAL"}
    ]
  }
}
```

**Frontend:**
- < 20 nodes: Mermaid diagram (lazy-loaded)
- >= 20 nodes: vis-network force graph (interactive, draggable)
- Toggle button to switch between views
- Node colors from GRAPH_SCHEMA.md entity type definitions
- Click node to see properties, click edge to see relationship details
- Fullscreen button for large graphs

### 3. Link Pills (`card_type: "links"`)

**Source tools:** `derive_xcallback_url`, `link_resolver.py` (via any tool)

```
[noteplan:// Goals.md]  [mailto: omar@...]  [github: omars-lab/...]  [maps: Austin, TX]
```

**SSE payload:**
```json
{
  "card_type": "links",
  "data": [
    {"url": "noteplan://x-callback-url/openNote?filename=Goals.md", "type": "noteplan", "label": "Goals.md"},
    {"url": "mailto:omar@example.com", "type": "email", "label": "omar@example.com"},
    {"url": "https://github.com/omars-lab/knowledge-agents", "type": "github", "label": "knowledge-agents"},
    {"url": "https://maps.google.com/?q=Austin,TX", "type": "location", "label": "Austin, TX"}
  ]
}
```

**Frontend:** Colored clickable pill badges. Colors and behavior by type:

| Type | Color | Icon | Click Behavior |
|------|-------|------|---------------|
| noteplan | `#38bdf8` (blue) | app icon | `noteplan://` xcallback — opens NotePlan app directly (mobile/desktop) |
| quip | `#F2A93B` (orange) | quip logo | `https://*.quip.com/` — opens Quip doc in browser |
| vscode | `#007ACC` (vscode blue) | code brackets | `vscode://file/` — opens file in VS Code app |
| github | `#8b949e` (gray) | octocat | `https://github.com/` — opens in new browser tab |
| email | `#34d399` (green) | envelope | `mailto:` — opens mail client |
| location | `#f87171` (red) | pin | `https://maps.google.com` — opens in new tab + renders map card |
| web | `#a78bfa` (purple) | globe | `https://` — opens in new browser tab |

**Key distinction: xcallback vs HTML links.** NotePlan links use `noteplan://x-callback-url/...` which opens the native app — these should be styled differently (app icon, "Open in NotePlan" label) vs standard `https://` links that open in the browser. On mobile Safari, xcallback URLs trigger the app switcher; on desktop, they open the Mac app. The pill should indicate "opens app" vs "opens browser" so the user knows what to expect.

### 4. Map Embed (`card_type: "map"`)

**Source:** Links with `type: "location"`

```
+------------------------------------------------------------------+
| Austin, TX                                                        |
| +--------------------------------------------------------------+ |
| |                                                              | |
| |                    [OpenStreetMap embed]                      | |
| |                         * pin                                | |
| |                                                              | |
| +--------------------------------------------------------------+ |
| [Open in Google Maps]                                            |
+------------------------------------------------------------------+
```

**Frontend:** Leaflet + OpenStreetMap tile layer (free, no API key). Geocode the location name to lat/lng using Nominatim (free). Pin marker on the map. "Open in Google Maps" link as fallback.

### 5. Tool Detail Block (`card_type: "tool_detail"`)

**Source:** Enhanced `tool_complete` event (all tools)

```
+------------------------------------------------------------------+
| > query_knowledge_graph                        2.3s   $0.0012    |
+------------------------------------------------------------------+
  (click to expand)
  Model: claude-sonnet-4-20250514
  Input:  {"query": "MATCH..."}                  142 tokens
  Output: {"nodes": [...]}                       387 tokens
  Cost:   $0.0012
  Duration: 2.3s
  |████████░░░░░░░░░░|
+------------------------------------------------------------------+
```

**Frontend:** Collapsed: tool name, duration, cost. Expanded: model, input/output JSON (syntax-highlighted), token counts, duration bar.

### 6. Changelog Timeline (`card_type: "changelog"`)

**Source tool:** `knowledge_changelog`

```
+------------------------------------------------------------------+
| Knowledge Changelog: Mar 17 - Mar 24                              |
|                                                                   |
| Mar 24  ● New: "Qwen3.5-9B selected for summarization"          |
|         ● Updated: "LM Studio models" → added eval results       |
| Mar 22  ● New: "Chat UI plan created"                            |
|         ● Deleted: "Old auth middleware"                          |
| Mar 20  ● New: "Graphiti integration started"                    |
+------------------------------------------------------------------+
```

**SSE payload:**
```json
{
  "card_type": "changelog",
  "data": {
    "start_date": "2026-03-17",
    "end_date": "2026-03-24",
    "entries": [
      {"date": "2026-03-24", "action": "new", "summary": "Qwen3.5-9B selected for summarization", "entity": "Model Decision"},
      {"date": "2026-03-24", "action": "updated", "summary": "LM Studio models", "detail": "added eval results"}
    ]
  }
}
```

**Frontend:** Vertical timeline with colored dots by action type (green=new, blue=updated, red=deleted). Dates as section headers. Expandable detail on each entry.

## Implementation Phases

### Phase A: Backend — Structured Tool Returns (2 sessions)

**Scope:** Modify tools to return structured data alongside text.

1. **Add `structured` field to `tool_complete` SSE event** in `agent.py`
   - Parse tool handler return values for structured payloads
   - Emit structured data in `tool_complete` event
   - Backwards-compatible: `structured` is optional

2. **Update `semantic_search` tool** — return `note_cards` structured data
   - Include file_path, title (from filename), preview (first 200 chars), xcallback_url (via link_resolver), similarity_score, modified_at
   - Text summary still included for agent reasoning

3. **Update `query_knowledge_graph` tool** — return `graph` structured data
   - Parse Graphiti results into nodes/edges with types and colors from GRAPH_SCHEMA
   - Include entity properties and relationship labels

4. **Update `query_graph_cypher` tool** — return `graph` structured data
   - Parse Neo4j records into nodes/edges format
   - Apply color/shape from link_resolver entity type definitions

5. **Update `derive_xcallback_url` tool** — return `links` structured data
   - Include URL, type classification, label

6. **Update `knowledge_changelog` tool** — return `changelog` structured data
   - Parse markdown sections into date/action/summary entries

7. **Add `duration_ms` tracking** to all tool calls in agent.py
   - Timestamp tool_start, compute duration at tool_complete
   - Include in enriched `tool_complete` event

### Phase B: Frontend — Card Components (2 sessions)

**Scope:** Render structured SSE events as rich cards.

1. **Note Card component** — `renderNoteCard(data)`
   - Styled card with title, preview, similarity badge, xcallback button
   - CSS: card border-left colored by score, hover effect

2. **Graph Viewer component** — `renderGraph(data)`
   - Lazy-load mermaid.js on first graph event
   - Lazy-load vis-network on first graph with >=20 nodes
   - Mermaid/force-graph toggle button
   - Node click handler showing properties panel

3. **Link Pills component** — `renderLinks(data)`
   - Colored pill per link type
   - Click opens URL in new tab

4. **Map Embed component** — `renderMap(location)`
   - Lazy-load Leaflet + OpenStreetMap tiles
   - Nominatim geocoding for location name -> lat/lng
   - Pin marker, "Open in Google Maps" fallback link

5. **Tool Detail Block component** — `renderToolDetail(data)`
   - Collapsible block with chevron toggle
   - Duration bar (proportional to total response time)
   - Syntax-highlighted JSON for input/output

6. **Changelog Timeline component** — `renderChangelog(data)`
   - Vertical timeline with colored action dots
   - Date section headers, expandable entries

7. **Update SSE handler in chat.js** — route `tool_complete` events with `structured` field to the appropriate card renderer

### Phase C: Polish + Testing (1 session)

1. Card responsive design (mobile-friendly)
2. Card loading states (skeleton screens while data arrives)
3. Error states per card type
4. Integration tests: SSE -> card rendering pipeline
5. Update `docs/ARCHITECTURE.md` with card type flow diagram

## CDN Libraries (lazy-loaded)

| Library | Size | Purpose | Load Trigger |
|---------|------|---------|-------------|
| mermaid.js | 1.5 MB | Diagram rendering | First `graph` event with <20 nodes |
| vis-network | 200 KB | Force graph | First `graph` event with >=20 nodes |
| Leaflet | 40 KB | Map embed | First `map` event or location link |

## SSE Event Contract (After Implementation)

```
tool_start     → {"type": "tool_start", "name": "..."}
tool_input     → {"type": "tool_input", "chunk": "..."}
tool_complete  → {"type": "tool_complete", "name": "...", "input": "...",
                   "output_text": "...",
                   "structured": {"card_type": "...", "data": ...},
                   "duration_ms": 2300, "model": "..."}
text           → {"type": "text", "content": "..."}
result         → {"type": "result", "session_id": "...", "cost_usd": 0.05,
                   "turns": 3, "duration_ms": 5000}
error          → {"type": "error", "message": "..."}
rate_limit     → {"type": "rate_limit", "status": "...", "utilization": 0.95}
```

## Backwards Compatibility

- `structured` field is optional on `tool_complete` — old frontends ignore it
- `text` events still carry the full agent response — cards are supplementary, not replacement
- Tools still return text summaries for agent reasoning — structured data is a parallel channel
- No breaking changes to existing SSE consumers

## Test Plan

### Unit Tests (`tst/unit/chat/`)

**Note classifier tests** (`test_note_classifier.py`):
- `Calendar/20260325.md` -> `daily`
- `Calendar/2026-W13.md` -> `weekly`
- `Templates/Weekly Review.md` -> `template`
- Note with `quip_url` in frontmatter -> `quip`
- Note with inline `https://company.quip.com/abc123` -> `quip`
- `Notes/Chat UI Plan.md` -> `plan`
- `Notes/Project Knowledge Agents.md` -> `project`
- `Notes/Random Thoughts.md` -> `note`
- `src/knowledge_agents/server.py` via `classify_file_path` -> `file` with `language: Python`
- NotePlan paths return `None` from `classify_file_path`

**Card rendering tests** (`test_card_rendering.py`):
- Each card type renders correct HTML structure
- Note card shows correct icon/color for each note_type
- xcallback links get "Open in NotePlan" label + app icon
- vscode links get "Open in VS Code" label + code icon
- Quip links get "Open in Quip" label + quip icon
- https links get globe icon
- Similarity badge shows correct color gradient
- Task stats progress bar renders correctly
- Graph viewer selects mermaid vs force-graph based on node count

**SSE structured event tests** (`test_structured_events.py`):
- `tool_complete` with `structured` field parses correctly
- `tool_complete` without `structured` falls back to pill-only rendering
- Each `card_type` routes to correct renderer
- Malformed structured payloads don't crash the UI (graceful fallback to text)

### Integration Tests (`tst/unit/chat/test_chat_ui.py` — extend existing)

**Backend structured output tests** (requires claude-agent running):
- `semantic_search` tool returns `note_cards` structured data with valid xcallback URLs
- `query_graph_cypher` returns `graph` structured data with nodes/edges
- `derive_xcallback_url` returns `links` structured data
- `tool_complete` SSE events include `duration_ms`
- Structured payloads are valid JSON

**End-to-end card rendering tests** (requires both containers):
- Send query that triggers `semantic_search` -> verify note cards appear in response
- Send query that triggers graph tool -> verify graph data in SSE stream
- Verify xcallback URLs are well-formed (`noteplan://x-callback-url/...`)
- Verify vscode URLs are well-formed (`vscode://file/...`)

### Demo Mode — Sample Conversation with All Card Types

A hardcoded demo conversation that exercises every card type, available at `http://localhost:8080/?demo=true`. This enables:
- Frontend development without running the agent stack
- Visual regression testing of all card types
- Browser-based verification via Chrome DevTools
- Showcasing the UI to stakeholders

**Implementation:** `chat/demo.js` — injects a mock SSE event sequence when `?demo=true` is in the URL. The demo replays events with realistic delays (50ms between text tokens, 200ms between tool events) to simulate real streaming.

**Demo conversation script:**

```
User: "Show me everything — notes about goals, the knowledge graph, and my changelog"

SSE Events (simulated):

1. tool_start: semantic_search
2. tool_complete: semantic_search
   structured: note_cards (6 cards, one per note_type)
     - daily:    Calendar/20260325.md (3/5 tasks)
     - weekly:   Calendar/2026-W13.md
     - plan:     Notes/Chat UI Plan.md (8/12 tasks, Active)
     - template: Templates/Weekly Review.md
     - quip:     Notes/Q2 OKRs.md (quip_url: https://company.quip.com/abc123)
     - note:     Notes/Goals.md (92% match)

3. text: "I found 6 notes related to goals. Let me also check the knowledge graph..."

4. tool_start: query_knowledge_graph
5. tool_complete: query_knowledge_graph
   structured: graph (12 nodes, 18 edges)
     - nodes: Goals(Topic), Chat UI(Project), Omar(Person), 2026(Date), ...
     - edges: HAS_GOAL, WORKS_ON, CREATED_IN, DEPENDS_ON, ...

6. text: "Here's the knowledge graph showing how your goals connect..."

7. tool_start: derive_xcallback_url
8. tool_complete: derive_xcallback_url
   structured: links
     - noteplan://x-callback-url/openNote?filename=Goals.md
     - vscode://file/src/knowledge_agents/claude_agent/server.py
     - https://company.quip.com/abc123/Q2-OKRs
     - https://github.com/omars-lab/knowledge-agents
     - mailto:omar@example.com
     - https://maps.google.com/?q=Austin,TX

9. text: "I also found a location reference. Here's Austin on the map..."

10. structured: map (location: "Austin, TX", lat: 30.2672, lng: -97.7431)

11. tool_start: knowledge_changelog
12. tool_complete: knowledge_changelog
    structured: changelog (Mar 17 - Mar 24, 8 entries)

13. text: "Here's your changelog for the past week..."

14. result: session_id, cost_usd: 0.0349, turns: 2, duration_ms: 5000
```

**File card demo** — also include a `tool_complete` with `structured: note_cards` containing a `file` type card:
```json
{"file_path": "src/knowledge_agents/claude_agent/server.py", "note_type": "file",
 "title": "server.py", "preview": "FastAPI server for the Claude Agent...",
 "language": "Python", "vscode_url": "vscode://file/.../server.py"}
```

**Demo mode toggle:**
```javascript
// In chat.js
const DEMO_MODE = new URLSearchParams(window.location.search).has("demo");
if (DEMO_MODE) {
  import("./demo.js").then(m => m.runDemo());
}
```

**Test workflow:**
1. `docker compose up -d chat` (only nginx needed)
2. Open `http://localhost:8080/?demo=true`
3. All card types render in sequence with simulated streaming
4. Screenshot each card type for visual regression baseline
5. Compare after CSS/JS changes

### Browser Tests (manual verification via Chrome DevTools)

- [ ] Note cards render with correct type icons and accent colors
- [ ] "Open in NotePlan" button triggers xcallback:// (test on macOS)
- [ ] "Open in VS Code" button triggers vscode:// (test on macOS)
- [ ] "Open in Quip" button opens browser tab
- [ ] Graph viewer renders Mermaid for small graphs
- [ ] Graph viewer switches to force-graph for large graphs
- [ ] Tool detail block expands/collapses with animation
- [ ] Map embed loads OpenStreetMap tiles
- [ ] Mobile: cards stack full-width, no horizontal overflow
- [ ] Dark theme: all card types readable, no contrast issues

## Skills to Update

| Skill | Update Needed |
|-------|---------------|
| `/knowledge` | Document new card types in output section. Mention that queries return rich cards (note cards, graphs, maps) in addition to text. |
| `/deploy` | Add `note_classifier.py` to key files list if it becomes a new module. |
| `/extend-agent` | Update tool return format docs — tools now return both text and `structured` payload. |
| `/extend-eval` | Add eval cases for structured output: verify card_type, data shape, xcallback URL format. |
| `/agent-debug` | Add debugging tips for structured events: check `tool_complete` SSE events in browser DevTools console for `structured` field. |

## Living Documents to Update

| Document | Update |
|----------|--------|
| `docs/ARCHITECTURE.md` | Add card type flow diagram (SSE -> card renderer -> DOM) |
| `docs/GRAPH_SCHEMA.md` | Document SSE card type contracts, note_type enum |
| `docs/USE_CASES.md` | Add use cases for each card type with links to code |
| `docs/OBSERVABILITY.md` | Add structured event metrics (card type counts in Prometheus) |
| `CLAUDE.md` | Add note_type classification to coding rules if it becomes a pattern |

## Key Files to Modify

| File | Changes |
|------|---------|
| `src/knowledge_agents/claude_agent/agent.py` | Enrich `tool_complete` with output, duration_ms, structured |
| `src/knowledge_agents/claude_agent/tools.py` | Return structured payloads from tool handlers |
| `src/knowledge_agents/claude_agent/note_classifier.py` | New: classify notes by type (daily, plan, quip, file, etc.) |
| `src/knowledge_agents/claude_agent/link_resolver.py` | Expose entity colors/shapes as structured data, add vscode:// and quip URL support |
| `chat/chat.js` | Add card renderers, route structured events, demo mode toggle |
| `chat/demo.js` | New: mock SSE event sequence exercising every card type |
| `chat/chat.css` | Card styles for each type (8 note types + graph + map + tool detail + changelog) |
| `chat/index.html` | Lazy-load script tags for mermaid, vis-network, leaflet |
| `docs/GRAPH_SCHEMA.md` | Document SSE card type contracts |
| `tst/unit/chat/test_note_classifier.py` | New: note classification tests |
| `tst/unit/chat/test_card_rendering.py` | New: card HTML structure tests |
| `tst/unit/chat/test_structured_events.py` | New: SSE structured event parsing tests |

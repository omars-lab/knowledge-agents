# Claude Agent Interaction Experience: Subagent + Docs + On-Demand Graphs

## Context

The Claude Agent is fully functional (container, API, tools, evals) but has no user-facing interaction surface beyond `curl` and `make claude-agent-chat`. It's not documented in the README, can't be invoked from Claude Code, and has no graph visualization.

**Goal:** Make the Claude Agent usable from Claude Code as a `/knowledge` skill, add on-demand SVG graph rendering, and update the README.

**User decisions:**
- Primary interface: **Claude Code subagent** (invoke via `/knowledge` skill)
- SVG graphs: **On-demand** (only when explicitly requested)

## Plan

### Step 1: Create `/knowledge` Claude Code skill

**File:** `.claude/skills/knowledge.md`

A user-invocable skill that proxies queries to the Claude Agent API. When invoked:
1. Checks if the claude-agent container is running (health check)
2. Sends the user's query to `POST /api/v1/chat`
3. Displays the response (tools used, answer, cost)
4. If the user asks for a graph, calls a graph rendering step (Step 2)
5. Maintains session_id across follow-up invocations

Usage patterns:
```
/knowledge what notes do I have about AI projects?
/knowledge read Calendar/20251218.md and summarize it
/knowledge build a knowledge graph from my recent notes
/knowledge show me a graph of entities related to "machine learning"
```

The skill instructs Claude Code to:
- Call the agent API via curl
- Parse the JSON response
- Display the answer text
- If graph data is present or requested, invoke the SVG renderer

### Step 2: Add SVG graph rendering tool

**File:** `scripts/render_graph.py`

A standalone Python script that queries Neo4j and renders an SVG using `graphviz` (or `pyvis` for interactive HTML). Called on-demand when the user asks for a visualization.

```bash
python scripts/render_graph.py \
  --query "MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 50" \
  --output build/graphs/knowledge-graph.svg \
  --format svg
```

Features:
- Accepts a Cypher query or entity name as input
- Renders nodes (color-coded by type: Person, Project, Topic, etc.)
- Renders edges with relationship labels
- Outputs SVG (viewable in browser, embeddable) or HTML (interactive)
- Saves to `build/graphs/` with timestamped filenames

Dependencies: `graphviz` Python package (lightweight, no JS needed for SVG)

### Step 3: Add graph rendering as a Makefile target

**File:** `Makefile`

```makefile
claude-agent-graph: ## Render knowledge graph as SVG (usage: make claude-agent-graph QUERY="entity name or cypher")
	python scripts/render_graph.py --query "$(QUERY)" --output build/graphs/latest.svg
	open build/graphs/latest.svg
```

### Step 4: Wire graph rendering into the `/knowledge` skill

**File:** `.claude/skills/knowledge.md`

When the user says "show me a graph" or "visualize", the skill:
1. Asks the agent to run a `query_knowledge_graph` call to get relevant entities
2. Passes the Cypher result to `scripts/render_graph.py`
3. Saves SVG to `build/graphs/{topic}-{date}.svg`
4. Shows the user the file path (Claude Code can display the image)

### Step 5: Update README.md

**File:** `README.md`

Add a new section documenting the Claude Agent:
- What it does (2-3 sentences)
- Quick start (`make claude-agent-up && make claude-agent-auth-seed`)
- How to use from Claude Code (`/knowledge`)
- How to use via curl
- API endpoints table
- Available tools
- Graph visualization
- Link to `docs/CLAUDE_AGENT_ARCHITECTURE.md` for details

### Step 6: Update CLAUDE.md commands section

**File:** `CLAUDE.md`

Add the `/knowledge` skill and graph rendering commands to the Key Commands section.

## Critical Files

| File | Change |
|------|--------|
| `.claude/skills/knowledge.md` | New: user-invocable `/knowledge` skill |
| `scripts/render_graph.py` | New: SVG graph renderer from Neo4j |
| `Makefile` | Add `claude-agent-graph` target |
| `README.md` | Add Claude Agent documentation section |
| `CLAUDE.md` | Add new commands |

## Verification

1. Test skill: `/knowledge read Calendar/20251218.md and summarize it`
2. Test graph: `make claude-agent-graph QUERY="MATCH (n:Entity) RETURN n LIMIT 20"`
3. Test from Claude Code: invoke `/knowledge` and verify response
4. Verify README renders correctly
5. Unit tests still pass: `make claude-agent-test`

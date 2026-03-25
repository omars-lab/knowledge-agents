---
name: knowledge-index
description: Sweep NotePlan files, extract entities/relationships, build knowledge graph in Neo4j
user_invocable: true
---

# /knowledge-index — Build a comprehensive knowledge graph from NotePlan files

Systematically sweep through NotePlan files, extract entities and relationships, and build a comprehensive knowledge graph in Neo4j. Tracks which files have been processed via git hashes to support incremental re-indexing.

## Graph Schema

### Node Types

| Label | Description | Key Properties |
|-------|-------------|----------------|
| `Note` | A NotePlan file | `file_path`, `last_processed`, `git_hash`, `file_type` (calendar/note) |
| `Entity` | An extracted concept | `name`, `type` |

### Entity Types

Extract these from note content:

| Type | Examples | When to use |
|------|----------|-------------|
| `Person` | Names of people | Any person mentioned |
| `Project` | Project names, initiatives | Named projects, repos, work items |
| `Topic` | Subject areas | Broad themes (AI, fitness, finance) |
| `Concept` | Ideas, frameworks | Specific ideas or mental models |
| `Organization` | Companies, teams | Named organizations |
| `Tool` | Software, services | Apps, tools, libraries |
| `Location` | Places | Cities, offices, venues |
| `Event` | Meetings, milestones | Named events with dates |
| `Date` | Specific dates | Important dates referenced |

### Relationship Types

| Type | Meaning | Example |
|------|---------|---------|
| `CONTAINS` | Note → Entity | A note mentions an entity |
| `RELATED_TO` | Entity → Entity | General connection |
| `WORKS_ON` | Person → Project | Person involved in project |
| `MENTIONS` | Note → Entity | Direct reference |
| `REFERENCES` | Entity → Entity | One concept references another |
| `OCCURS_AT` | Event → Date/Location | Event timing or location |
| `BELONGS_TO` | Entity → Organization | Membership |
| `PART_OF` | Entity → Entity | Hierarchical containment |

## Indexing Strategy

### Step 1: Discover files to process

List all NotePlan files and check which need indexing:

```bash
# Get current git hash of the noteplan directory (or file modification times)
find /noteplan -name "*.md" -newer build/graphs/.last_index_timestamp 2>/dev/null | head -50
```

Or via the agent:
```
/knowledge query the graph: MATCH (n:Note) RETURN n.file_path, n.git_hash ORDER BY n.last_processed DESC LIMIT 20
```

### Step 2: Determine delta

Compare current files against what's already indexed:

1. **List indexed files** from Neo4j:
   ```
   MATCH (n:Note) RETURN n.file_path, n.git_hash, n.last_processed
   ```

2. **List current files** from the filesystem:
   ```bash
   find /noteplan/Calendar -name "*.md" -mtime -30  # last 30 days
   find /noteplan/Notes -name "*.md" -not -path "*/@Trash/*"
   ```

3. **Compute delta**: files that are new or modified since `last_processed`

### Step 3: Process each file

For each file in the delta, use the `/knowledge` agent:

```
/knowledge read Calendar/20251218.md and extract all entities (people, projects, topics, concepts, tools, events) and relationships. Then build a knowledge graph from them.
```

Use multi-turn for reliability (one tool per turn):
1. **Turn 1**: "Read {file_path} and list the entities you can extract"
2. **Turn 2**: "Build a knowledge graph from those entities"

### Step 4: Mark file as indexed

After processing, the `build_knowledge_graph` tool sets `Note.last_processed = datetime()` on the Note node. To also track the file hash:

```
/knowledge query the graph: MATCH (n:Note {file_path: 'Calendar/20251218.md'}) SET n.git_hash = 'abc123' RETURN n
```

Note: `query_knowledge_graph` is read-only and blocks SET. The git_hash tracking must be done via `build_knowledge_graph` or a separate update mechanism (future enhancement).

### Step 5: Verify

After indexing, check the graph:
```
/knowledge how many entities and notes are in the knowledge graph?
/knowledge show me a graph of the most connected entities
```

Or via Makefile:
```bash
make claude-agent-graph  # Render full graph as SVG
```

## Batch Indexing Approach

For processing many files, use a script that calls the agent API sequentially:

```bash
# Process last 7 days of calendar notes
for file in $(find /path/to/noteplan/Calendar -name "*.md" -mtime -7 | sort); do
    relative=$(echo "$file" | sed 's|.*/Calendar/|Calendar/|')
    echo "Processing: $relative"

    # Turn 1: Read and extract
    SESSION=$(curl -s -X POST http://localhost:8004/api/v1/chat \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"Read $relative and list the entities you find\"}" \
        | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

    sleep 3  # Rate limit spacing

    # Turn 2: Build graph
    curl -s -X POST http://localhost:8004/api/v1/chat \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"Build a knowledge graph from those entities\", \"session_id\": \"$SESSION\"}"

    sleep 5  # Rate limit spacing between files
done
```

## Incremental Re-indexing

To re-index only changed files:

1. Check the timestamp of the last full index:
   ```bash
   stat -f %m build/graphs/.last_index_timestamp 2>/dev/null || echo "0"
   ```

2. Find files modified since then:
   ```bash
   find /noteplan -name "*.md" -newer build/graphs/.last_index_timestamp
   ```

3. Process only the delta files

4. Update the timestamp:
   ```bash
   touch build/graphs/.last_index_timestamp
   ```

## Recommended Processing Order

1. **Recent calendar notes first** (last 30 days) — most relevant, highest signal
2. **Project notes** — `Notes/` directory, excluding `@Trash/`
3. **Older calendar notes** — fill in historical context
4. **Prompts and templates** — low priority, mostly meta-content

## Rate Limiting Considerations

- The Claude Agent uses Claude API with subscription-tier rate limits
- Each file requires 2 API calls (read + build) at ~$0.03-0.05 per file
- Space requests with `--delay 5` in the eval runner, or `sleep 5` in scripts
- Processing 100 files costs ~$3-5 and takes 30-60 minutes
- Start with a small batch (10 files) to verify quality before scaling

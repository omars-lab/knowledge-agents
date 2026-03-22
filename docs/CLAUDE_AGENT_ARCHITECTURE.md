# Claude Agent Architecture

Multi-turn conversational Claude agent for interactive note search, knowledge graph building, and graph exploration.

## System Topology

```mermaid
graph TB
    subgraph "Docker Compose Stack"
        subgraph "Claude Agent Service (NEW)"
            CA[claude-agent<br/>FastAPI :8004]
            SDK[Claude Agent SDK<br/>ClaudeSDKClient]
            TOOLS[In-Process MCP Server<br/>semantic_search<br/>read_note<br/>build_knowledge_graph<br/>query_knowledge_graph<br/>derive_xcallback_url]
        end

        subgraph "Shared Infrastructure"
            QDR[Qdrant Vector Store<br/>:6333]
            NEO[Neo4j :7474/:7687]
            TMCP[tidy-mcp<br/>:8003]
            PROXY[llm-proxy :4000<br/>embeddings only]
        end

        subgraph "Existing Services"
            API[agentic-api :8001]
            PG[PostgreSQL :5432]
            PROM[Prometheus :9090]
        end
    end

    subgraph "External"
        CLAUDE[Anthropic Claude API]
        LMS[LM Studio<br/>Local Models]
    end

    subgraph "Host"
        CREDS[~/.claude]
        NOTES[NotePlan Notes<br/>mounted :ro]
    end

    CA --> SDK --> CLAUDE
    CA --> TOOLS
    TOOLS --> QDR
    TOOLS --> NEO
    TOOLS --> TMCP
    TOOLS -.->|embeddings| PROXY --> LMS
    CREDS -.->|mount :ro| CA
    NOTES -.->|mount :ro| CA
    API --> PROXY
```

## Multi-Turn Streaming Flow

```mermaid
sequenceDiagram
    participant User
    participant Server as claude-agent<br/>FastAPI
    participant SDK as query() / ClaudeSDKClient<br/>StreamEvent streaming
    participant Claude as Anthropic API
    participant Tools as MCP Tools

    Note over User,Tools: Turn 1: Initial query (streaming)
    User->>Server: POST /api/v1/chat/stream {message, session_id: null}
    Server->>SDK: query(prompt, options={include_partial_messages: true})

    loop StreamEvent processing
        SDK->>Claude: System prompt + user message
        Claude-->>SDK: StreamEvent: content_block_start (tool_use)
        SDK-->>Server: SSE: tool_start
        Server-->>User: SSE event

        SDK->>Tools: Execute semantic_search
        Tools-->>SDK: results
        SDK->>Claude: tool_result

        Claude-->>SDK: StreamEvent: text_delta
        SDK-->>Server: SSE: text
        Server-->>User: SSE event (streamed text)
    end

    SDK-->>Server: ResultMessage (session_id, cost, turns)
    Server-->>User: SSE: result

    Note over User,Tools: Turn 2: Follow-up (same session, streaming)
    User->>Server: POST /api/v1/chat/stream {message, session_id: "abc123"}
    Note over SDK: Resumes session context
```

## Comparison with Existing Agents

```mermaid
flowchart LR
    subgraph "Existing: One-Shot Agents"
        direction TB
        A1[note_query_agent] -->|single request| A2[Answer + files]
        A3[graph_builder_agent] -->|single file| A4[Entities + relationships]
    end

    subgraph "New: Multi-Turn Claude Agent"
        direction TB
        B1[User conversation] -->|turn 1| B2[Search notes]
        B2 -->|turn 2| B3[Build graph from results]
        B3 -->|turn 3| B4[Query graph for patterns]
        B4 -->|turn N| B5[Explore, refine, iterate]
    end

    style A1 fill:#fff3e0
    style A3 fill:#fff3e0
    style B1 fill:#e8f5e9
```

## Container Architecture

```mermaid
graph TB
    subgraph "claude-agent container"
        UV[uvicorn :8000] --> FA[FastAPI App]
        FA -->|creates per session| CLI[query / ClaudeSDKClient<br/>Claude Agent SDK]

        subgraph "Mounted Volumes"
            CRED[~/.claude -> /home/agent/.claude :ro]
            SRC[./src -> /app/src]
        end
    end

    CLI -->|reads auth| CRED
```

## Tools (5 Custom MCP Tools)

All defined via `@tool()` decorator, registered as in-process MCP server.

| Tool | Purpose | Reuses |
|------|---------|--------|
| `semantic_search(query, limit)` | Search notes via Qdrant | `query_vector_store.py` pattern |
| `read_note(file_path)` | Read note file content | `notes.parser.read_noteplan_file()` |
| `build_knowledge_graph(file_paths)` | Extract entities to Neo4j | `graph_utils.create_graph_nodes_and_relationships()` |
| `query_knowledge_graph(cypher_query)` | Query Neo4j graph | Direct Cypher execution |
| `derive_xcallback_url(file_path, heading)` | Generate NotePlan links | `noteplan_tools.py` pattern |

## Combined Vector + Graph Workflow

```
User: "What are my notes about machine learning connected to?"

Agent workflow:
1. semantic_search("machine learning") -> finds 5 relevant note files
2. read_note(top_result) -> reads the content
3. build_knowledge_graph([file1, file2, ...]) -> creates graph nodes/edges
4. query_knowledge_graph("MATCH (n:Note)-[:CONTAINS]->(e:Entity)
     WHERE n.file_path IN [...] RETURN e.name, e.type") -> entities in those notes
5. query_knowledge_graph("MATCH (e1:Entity)-[r]->(e2:Entity)
     WHERE e1.name IN [...] RETURN e1.name, type(r), e2.name") -> relationships
6. Synthesize answer about connections
```

## Session Workspace

Each agent session gets its own folder in `build/sessions/`:

```
build/sessions/{session_id}/
    session.json              # Session metadata
    turns/
        turn_001_prompt.md    # User message
        turn_001_response.md  # Agent response
        turn_001_tools.json   # Tool calls + results
    search_results/
        search_001.json       # Qdrant results
    graphs/
        extraction_001.json   # Entity/relationship extraction
        cypher_queries.log    # All Cypher queries executed
    eval/
        session_score.json    # Eval scores
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/chat` | POST | Send message, get full response (buffered) |
| `/api/v1/chat/stream` | POST | Send message, get SSE stream (real-time) |
| `/api/v1/sessions` | GET | List active sessions |
| `/api/v1/sessions/{id}` | DELETE | Close a session |
| `/api/v1/sessions/{id}/artifacts` | GET | List session files |

## Key Design Decisions

1. **Streaming-first with `StreamEvent`** -- Uses `query()` with `include_partial_messages=True` for real-time SSE streaming
2. **`query()` with `resume` for multi-turn** -- The SDK handles session state internally
3. **Agent-driven tool selection** -- Claude decides which tools to use based on conversation
4. **Neo4j CE containerized** -- Full Cypher support, zero migration cost from existing code
5. **Dual-store (Qdrant + Neo4j)** -- Vector search for discovery, graph for relationship traversal
6. **Reuse existing graph utilities** -- Entity extraction by Claude, storage via `graph_utils`
7. **Eval as first-class feature** -- Lives in `evals/`, separate from `tst/`

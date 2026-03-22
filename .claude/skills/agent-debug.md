# /agent-debug — Debug a failing agent interaction

Debug workflow for Claude Agent issues.

## Steps

1. **Reproduce the query** via curl to the streaming endpoint:
   ```bash
   curl -N -X POST http://localhost:8004/api/v1/chat/stream \
     -H "Content-Type: application/json" \
     -d '{"message": "YOUR FAILING QUERY HERE"}'
   ```

2. **Read SSE stream events** to identify where the agent went wrong:
   - Look for `tool_start` events — did the right tool get called?
   - Check `tool_input` — was the input well-formed?
   - Check `tool_complete` — did the tool return results or errors?
   - Check `text` events — did the agent produce a response?
   - Check `result` — was there an error in the final result?

3. **Check tool responses**:
   - Did `semantic_search` return results? (Qdrant connectivity)
   - Did `build_knowledge_graph` succeed? (Neo4j connectivity)
   - Did `query_knowledge_graph` return data? (Cypher correctness)
   - Did `derive_xcallback_url` work? (tidy-mcp connectivity)

4. **Check container logs**:
   ```bash
   make claude-agent-logs
   ```
   Look for ERROR or WARNING lines in the Python logs.

5. **Check service health**:
   ```bash
   curl http://localhost:8004/health
   curl http://localhost:6333/readyz    # Qdrant
   curl http://localhost:7474           # Neo4j browser
   curl http://localhost:8003/health    # tidy-mcp
   curl http://localhost:4000/health    # llm-proxy
   ```

6. **Check session workspace** for artifacts:
   - `build/sessions/{session_id}/turns/` — prompts and responses
   - `build/sessions/{session_id}/search_results/` — Qdrant results
   - `build/sessions/{session_id}/graphs/` — Neo4j operations

7. **Suggest fixes** based on findings:
   - Prompt changes (update `prompts.py`)
   - Tool fixes (update `tools.py`)
   - Config changes (update `config.py` or docker-compose env vars)
   - Service issues (restart services, check connectivity)

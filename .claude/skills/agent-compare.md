# /agent-compare — Compare Claude agent vs existing agent

Side-by-side comparison of the Claude agent and the existing note query agent.

## Steps

1. **Send the same query to both endpoints**:

   Existing agent (agentic-api :8001):
   ```bash
   curl -s -X POST "http://localhost:8001/api/v1/notes/query" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $API_KEY" \
     -d '{"query": "YOUR QUERY HERE"}' | jq .
   ```

   Claude agent (claude-agent :8004):
   ```bash
   curl -s -X POST "http://localhost:8004/api/v1/chat" \
     -H "Content-Type: application/json" \
     -d '{"message": "YOUR QUERY HERE"}' | jq .
   ```

2. **Compare results** across dimensions:

   | Dimension | Existing Agent | Claude Agent |
   |-----------|---------------|--------------|
   | Response quality | Check `answer` field | Check `response` field |
   | Relevant files | Check `relevant_files` | Check if files mentioned in response |
   | Cost | Free (local LLM) | Check `metadata.cost_usd` |
   | Latency | Check response time | Check `metadata.duration_ms` |
   | Tools used | Guardrails + OpenAI agent | Check `tools_used` |
   | Multi-turn | Not supported | Check session_id continuity |
   | Graph building | Separate service | Integrated tool |

3. **Output a comparison table** with the results

4. **Notes**:
   - The existing agent uses local LLM models (free, slower)
   - The Claude agent uses Anthropic API (paid, faster, higher quality)
   - The Claude agent supports multi-turn and graph exploration
   - The existing agent has input/output guardrails

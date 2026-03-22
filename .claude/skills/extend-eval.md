# /extend-eval — Add eval test cases or datasets

Guide for adding new eval test cases to the Claude Agent eval framework.

## Steps

1. **Choose the eval dataset** to extend:
   - `evals/claude_agent/datasets/note_search.json` — Note query evals
   - `evals/claude_agent/datasets/graph_building.json` — Graph extraction evals
   - `evals/claude_agent/datasets/multi_turn.json` — Multi-turn conversation evals
   - `evals/claude_agent/datasets/tool_selection.json` — Tool selection evals
   - Or create a new dataset file

2. **Add test case(s)** with this structure:
   ```json
   {
     "id": "unique-id",
     "description": "What this tests",
     "turns": [
       {"input": "User message for turn 1"},
       {"input": "User message for turn 2 (optional)"}
     ],
     "expected": {
       "tools_used": ["semantic_search"],
       "output_contains": ["keyword"],
       "output_not_contains": ["I cannot"],
       "session_created": true,
       "session_maintained": true
     },
     "grading": {
       "dimension_name": "What to look for when grading"
     },
     "tags": ["category"]
   }
   ```

3. **Run the new eval case** to baseline:
   ```bash
   make claude-agent-eval
   ```

4. **Review results** in `evals/claude_agent/results/`

5. **If score is low**, suggest prompt improvements:
   - Check `src/knowledge_agents/claude_agent/prompts.py`
   - Consider adding workflow guidance or tool usage examples
   - Re-run eval after changes to verify improvement

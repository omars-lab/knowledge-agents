# /run-eval — Execute eval suite and show report

Run the Claude Agent eval suite and present results.

## Steps

1. **Run the eval suite**:
   ```bash
   make claude-agent-eval
   ```

2. **Read results** from `evals/claude_agent/results/`:
   - Find the latest result JSON files
   - Parse scores by dimension

3. **Generate and display report**:
   ```bash
   make claude-agent-eval-report
   ```

4. **Summarize scores** by dimension:
   - Tool selection: Did the agent pick the right tools?
   - Response quality: Did answers address the questions?
   - Session continuity: Did multi-turn context carry over?
   - Cost efficiency: API cost per eval case

5. **Highlight regressions** vs previous run (if available):
   - Compare overall scores
   - Flag any cases that went from PASS to FAIL

6. **Suggest improvements** for low-scoring cases:
   - Check which tools were expected vs used
   - Review the system prompt for missing guidance
   - Consider adding workflow examples to prompts.py

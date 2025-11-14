# Debugging: Empty `relevant_files` but Answer Mentions Files

## Problem

The API response shows:
- `relevant_files: []` (empty)
- But the answer mentions files like "2024-01-15.md", "2024-01-16.md", "notes/ideas.md"

## Root Cause

The semantic search is returning **zero results**, so `relevant_files` is correctly empty. However, the agent is still mentioning files because:

1. **Prompt Examples**: The prompt template includes example files (2024-01-15.md, 2024-01-16.md, notes/ideas.md) in the examples section
2. **Agent Hallucination**: The agent might be referencing files from examples or previous context
3. **No Semantic Match**: The query "genai/llms" doesn't match any embeddings in the vector store

## How to Debug

### 1. Check if Vector Store is Seeded

```bash
# Check if collection exists and has data
docker compose exec qdrant curl -s "http://localhost:6333/collections/app_actions_collection" | jq .
```

### 2. Check Semantic Search Logs

Look for these log messages:
```
INFO - Performing semantic search for note files: ...
INFO - Found X relevant note files
```

If you see "Found 0 relevant note files", semantic search returned empty.

### 3. Test Semantic Search Directly

```bash
# Run a test to see what semantic search returns
make integration-test-one TEST="tst/integration/database/test_vector_store.py::TestNotePlanVectorStoreSearch::test_semantic_search_project_ideas"
```

### 4. Check if Files About GenAI/LLMs Exist

```bash
# List all files in the vector store
docker compose exec qdrant curl -s "http://localhost:6333/collections/app_actions_collection/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{"limit": 100}' | jq '.result.points[].payload.file_name'
```

### 5. Re-seed Vector Store

If the vector store is empty or missing files:

```bash
# Re-seed the vector store
make db-seed-vector-store
```

## Why This Happens

1. **Query Mismatch**: "genai/llms" might not match the actual content in your notes
   - Try: "generative AI", "large language models", "AI", "machine learning"
   
2. **Vector Store Not Seeded**: The collection might be empty
   - Solution: Run `make db-seed-vector-store`

3. **Embedding Model Mismatch**: If embeddings were created with a different model
   - Solution: Re-seed with current embedding model

4. **Low Similarity Scores**: Results might be filtered out if similarity is too low
   - Check: Look at similarity scores in logs

## Expected Behavior

When semantic search returns **empty results**:
- `relevant_files: []` ✅ (correct)
- Prompt says: "No relevant note files found via semantic search." ✅
- Agent should say: "I couldn't find any files about genai/llms in your notes" ✅

## Fix: Improve Agent Prompt

The agent is currently mentioning files from examples. We should update the prompt to:
1. Only mention files that were actually found in semantic search
2. Not reference example files as if they're real

## Quick Test

```bash
# Test with a query that should match
make test-api QUERY="What are my tasks for today?" API_KEY="$(cat secrets/openai_api_key.txt | tr -d '\n')"

# Check if relevant_files is populated
# If still empty, check vector store seeding
```


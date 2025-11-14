# Testing Guide: API Token Header Authentication

This guide shows how to test the new API token header-based authentication system.

## Prerequisites

1. **Generate an API Key** (if you don't have one):
   ```bash
   make litellm-generate-api-token
   ```
   This creates/updates `secrets/openai_api_key.txt`

2. **Ensure Services Are Running**:
   ```bash
   make docker-up
   # Wait for services to be healthy
   make wait-for-services
   ```

## Testing Methods

### 1. Quick Test via Makefile (Recommended)

**Test with auto-loaded API key** (reads from `secrets/openai_api_key.txt`):
```bash
make test-api QUERY="What are my tasks for today?"
```

**Test with explicit API key**:
```bash
make test-api QUERY="What are my tasks for today?" API_KEY="sk-your-token-here"
```

**Alternative Makefile target**:
```bash
make test-note-query-api QUERY="What are my tasks for today?"
```

### 2. Test with curl Directly

**From host machine** (if API is exposed on localhost:8000):
```bash
API_KEY=$(cat secrets/openai_api_key.txt | tr -d '\n')
curl -X POST "http://localhost:8000/api/v1/notes/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"query": "What are my tasks for today?"}' | jq .
```

**From Docker container**:
```bash
API_KEY=$(cat secrets/openai_api_key.txt | tr -d '\n')
docker compose exec test curl -X POST "http://agentic-api:8000/api/v1/notes/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"query": "What are my tasks for today?"}' | jq .
```

### 3. Test Failure Cases

**Test missing Authorization header** (should return 401):
```bash
docker compose run --rm test curl -X POST "http://agentic-api:8000/api/v1/notes/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are my tasks?"}' \
  -w "\nHTTP Status: %{http_code}\n"
# Expected: HTTP Status: 401
```

**Test invalid token format** (should return 401):
```bash
docker compose run --rm test curl -X POST "http://agentic-api:8000/api/v1/notes/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: InvalidFormat" \
  -d '{"query": "What are my tasks?"}' \
  -w "\nHTTP Status: %{http_code}\n"
# Expected: HTTP Status: 401
```

**Test invalid token** (should return error from LiteLLM):
```bash
docker compose run --rm test curl -X POST "http://agentic-api:8000/api/v1/notes/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-invalid-token" \
  -d '{"query": "What are my tasks?"}' \
  -w "\nHTTP Status: %{http_code}\n"
# Expected: HTTP Status: 500 (LiteLLM will reject invalid token)
```

### 4. Run Integration Tests

**Full integration test suite** (includes API token header tests):
```bash
# Prepare environment (first time only)
make test-note-query-prepare

# Run tests (fast iteration)
make test-note-query-validate
```

**Or run full e2e test**:
```bash
make test-note-query-e2e-fast
```

**Run specific test file**:
```bash
make integration-test-one TEST="tst/integration/api/test_note_query_api.py"
```

### 5. Verify API Key is Registered

**List all registered API tokens**:
```bash
make db-list-litellm-tokens
```

This shows all tokens registered in the LiteLLM database, including:
- Token hash
- Key name/alias
- Models accessible
- Expiration date
- User/team IDs

## Expected Behavior

### ✅ Success Case
- Request with valid `Authorization: Bearer <token>` header
- Returns 200 with query response
- Token is extracted and used for LiteLLM proxy calls

### ❌ Failure Cases
- **Missing header**: Returns 401 with message "Authorization header is required"
- **Invalid format**: Returns 401 with message "Invalid authorization header format"
- **Invalid token**: Returns 500 (LiteLLM proxy rejects the token)

## Troubleshooting

### "Authorization header is required" (401)
- Make sure you're including the `Authorization: Bearer <token>` header
- Check that the header name is exactly "Authorization" (case-sensitive)

### "Invalid authorization header format" (401)
- Format must be: `Authorization: Bearer <token>`
- No extra spaces, must have "Bearer" prefix

### "token_not_found_in_db" (500)
- The API token is not registered in LiteLLM database
- Generate a new token: `make litellm-generate-api-token`
- Verify token exists: `make db-list-litellm-tokens`

### Services not running
```bash
# Check service status
docker compose ps

# Start services
make docker-up

# Wait for health
make wait-for-services
```

## Testing Checklist

- [ ] Generate API key: `make litellm-generate-api-token`
- [ ] Test with Makefile: `make test-api QUERY="test"`
- [ ] Test missing header (should fail with 401)
- [ ] Test invalid format (should fail with 401)
- [ ] Run integration tests: `make test-note-query-validate`
- [ ] Verify token in database: `make db-list-litellm-tokens`


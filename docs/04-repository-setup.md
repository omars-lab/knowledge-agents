# Repository Setup Guide

## Overview

This guide provides step-by-step instructions for setting up the Knowledge Agents repository from scratch.

## Prerequisites

- Docker and Docker Compose installed
- Make installed (for convenience commands)
- Access to NotePlan directory (for seeding)
- LM Studio running locally (for LLM models)

## Initial Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd knowledge-agents
```

### 2. Configure Secrets

```bash
# Create secrets directory
mkdir -p secrets

# Add admin API key (default for LiteLLM proxy)
echo "sk-1234" > secrets/admin_api_key.txt

# Add OpenAI API key (if needed for fallback)
# echo "sk-your-key" > secrets/openai_api_key.txt
```

### 3. Build Docker Images

```bash
make build
```

This builds:
- Main application image
- LiteLLM proxy image
- Seeder image

### 4. Start Services

```bash
make start
```

This starts:
- PostgreSQL database (port 5432)
- Qdrant vector store (ports 6333, 6334)
- LiteLLM proxy (port 4000)
- FastAPI application (port 8000)

### 5. Seed Database and Vector Store

```bash
make db-seed
```

This:
- Creates database schema (Plans, Buckets, Tasks)
- Parses NotePlan files from mounted directory
- Seeds database with Plans/Buckets/Tasks
- Generates embeddings and seeds vector store

## Directory Structure

```
knowledge-agents/
├── src/
│   ├── knowledge_agents/    # Main application
│   └── notes/                # NotePlan parsing package
├── scripts/                  # Utility scripts
├── tst/                      # Tests
├── data/                     # Database schema
├── config/                   # Configuration files
└── secrets/                  # API keys (git-ignored)
```

## Configuration

### Environment Variables

The system uses Docker secrets and configuration files:

- **Secrets**: Stored in `secrets/` directory
  - `admin_api_key.txt`: LiteLLM proxy admin key
  - `openai_api_key.txt`: Optional OpenAI API key

- **LiteLLM Config**: `config/litellm_config.yaml`
  - Model definitions
  - API base URLs
  - Model aliases

### Docker Compose Configuration

Services are configured in `docker-compose.yml`:

- **postgres**: Database service
- **qdrant**: Vector store service
- **llm-proxy**: LiteLLM proxy service
- **app**: FastAPI application
- **seeder**: Seeding service (profile: seeding)

## Development Workflow

### Running Tests

```bash
# Run all tests
make test

# Run unit tests only
make unit-test

# Run integration tests only
make integration-test

# Run specific test
make unit-test-one TEST=tst/unit/notes/test_parser.py::TestMarkdownParsing::test_simple_h1
```

### Making Changes

1. Edit source code in `src/`
2. Rebuild if dependencies changed: `make build`
3. Restart services: `make restart`
4. Run tests: `make test`

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f app
docker compose logs -f llm-proxy
```

### Database Access

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U knowledge -d knowledge_workflow

# View tables
\dt

# Query plans
SELECT * FROM plans LIMIT 10;
```

## Verification

### Check Services

```bash
# Check service health
curl http://localhost:8000/health

# Check LiteLLM proxy
curl http://localhost:4000/health

# Check Qdrant
curl http://localhost:6333/readyz
```

### Test API

```bash
# Query notes
curl -X POST http://localhost:8000/api/v1/notes/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are my tasks today?"}'
```

### Check Metrics

```bash
# View Prometheus metrics
curl http://localhost:8000/metrics
```

## Troubleshooting

### Services Not Starting

1. Check Docker is running: `docker ps`
2. Check ports are available: `lsof -i :8000 -i :4000 -i :5432`
3. Check logs: `docker compose logs`

### Database Connection Issues

1. Verify PostgreSQL is healthy: `docker compose ps postgres`
2. Check database URL in config
3. Verify database schema exists

### Vector Store Issues

1. Verify Qdrant is healthy: `docker compose ps qdrant`
2. Check collection exists: `curl http://localhost:6333/collections`
3. Verify embeddings were generated

### LiteLLM Proxy Issues

1. Verify LM Studio is running
2. Check proxy logs: `docker compose logs llm-proxy`
3. Verify API key is correct
4. Test proxy directly: `curl http://localhost:4000/health`

### Seeding Issues

1. Verify NotePlan directory is mounted
2. Check seeder logs: `docker compose logs seeder`
3. Verify files exist in mounted directory
4. Check file permissions

## Next Steps

1. **Customize NotePlan Path**: Update volume mount in `docker-compose.yml`
2. **Configure Models**: Edit `config/litellm_config.yaml`
3. **Add Tests**: Create tests in `tst/` directory
4. **Extend API**: Add new endpoints in `src/knowledge_agents/routers/`

## Production Considerations

- Use environment variables for secrets (not files)
- Set up proper database backups
- Configure Qdrant persistence
- Set up monitoring and alerting
- Use production-grade LLM service
- Implement rate limiting
- Add authentication/authorization

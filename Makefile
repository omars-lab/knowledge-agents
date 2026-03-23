# Knowledge Agents - Build Automation
#
# FAST FEEDBACK LOOP - End-to-End Testing:
#   For fastest iteration during development:
#     1. Run `make test-note-query-prepare` once (2-5 min) to set up services and seed data
#     2. Run `make test-note-query-validate` repeatedly (10-30 sec) for fast test iteration
#     3. Run `make test-note-query-e2e-fast` (1-2 min) for quick checks with smart seeding
#     4. Run `make test-note-query-e2e-full` (2-5 min) after schema changes or when you need a clean slate
#
#   The `test-note-query-e2e` target is an alias for `test-note-query-e2e-fast` (backward compatibility)
#
# SERVICE HEALTH CHECKS:
#   All health check and helper logic has been moved to scripts/makefile-helper.sh
#   This script contains reusable functions for complex Makefile operations.

.PHONY: help start build test clean format lint type-check docker-up docker-down litellm litellm-embedding litellm-code tidy-mcp-up tidy-mcp-down tidy-mcp-restart tidy-mcp-logs tidy-mcp-test test-tools neo4j-seed-vector neo4j-seed-graph neo4j-build-graph neo4j-query neo4j-graph-builder-up neo4j-graph-builder-down neo4j-graph-builder-restart neo4j-graph-builder-logs claude-agent-up claude-agent-down claude-agent-logs claude-agent-test claude-agent-eval claude-agent-clean-sessions

# =============================================================================
# MAIN TARGETS
# =============================================================================

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

start: build docker-up ## Start the application (build + run)
	@echo "✅ Application started"

stop: docker-down ## Start the application (build + run)
	@echo "❌ Application stopped"

build: ## Build Docker images
	docker compose build

test: ## Run all tests
	docker compose run --rm -v $(PWD)/build:/app/build test pytest tst/ -v --cov=src --cov-report=html:build/reports/coverage --cov-report=term

conda-env-name := knowledge-agents

conda-setup: ## Set up conda environment with dev dependencies
	@echo "🔧 Setting up conda environment..."
	@if ! conda env list | grep -q "^$(conda-env-name) "; then \
		echo "📦 Creating conda environment: $(conda-env-name)"; \
		conda create -n $(conda-env-name) python=3.11 -y; \
	fi
	@echo "📥 Installing dependencies..."
	@conda run -n $(conda-env-name) pip install -q -r requirements-dev.txt
	@conda run -n $(conda-env-name) pip install -q -r requirements.txt || true
	@conda run -n $(conda-env-name) pip install -q markdown beautifulsoup4
	@echo "✅ Conda environment ready"

unit-tests: ## Run unit tests only (fast, no external dependencies) - Uses conda environment
	@echo "🧪 Running unit tests..."
	@echo "   This verifies dependency injection, client managers, and utilities work correctly"
	@echo "   No external services (DB, Qdrant, LiteLLM) required - runs in seconds"
	@if ! conda env list | grep -q "^$(conda-env-name) "; then \
		echo "❌ Conda environment '$(conda-env-name)' not found. Run 'make conda-setup' first."; \
		exit 1; \
	fi
	@conda run -n $(conda-env-name) pytest tst/unit/ -v -m "unit" --cov=src --cov-report=html:build/reports/coverage/unit --cov-report=term --tb=short
	@echo "✅ Unit tests completed"

test-unit: unit-tests ## Alias for unit-tests

integration-tests: ## Run integration tests only
	docker compose run --rm -v $(PWD)/build:/app/build test pytest tst/integration/ -v -m "integration" --cov=src --cov-report=html:build/reports/coverage/integration --cov-report=term

format: ## Format code with black and isort
	docker compose run --rm -v $(PWD)/src:/app/src -v $(PWD)/tst:/app/tst -v $(PWD)/scripts:/app/scripts test black /app/src /app/tst /app/scripts
	docker compose run --rm -v $(PWD)/src:/app/src -v $(PWD)/tst:/app/tst -v $(PWD)/scripts:/app/scripts test isort /app/src /app/tst /app/scripts

lint: ## Run linting
	docker compose run --rm -v $(PWD)/src:/app/src -v $(PWD)/tst:/app/tst -v $(PWD)/scripts:/app/scripts test flake8 /app/src /app/tst /app/scripts

type-check: ## Run type checking
	docker compose run --rm -v $(PWD)/src:/app/src test mypy /app/src --ignore-missing-imports

# =============================================================================
# DOCKER TARGETS
# =============================================================================

docker-up: ## Start Docker containers
	docker compose up -d --build

docker-down: ## Stop Docker containers
	docker compose down

docker-clean: ## Clean Docker containers and images
	docker compose down --volumes --remove-orphans
	docker system prune -f

tidy-mcp-up: ## Start tidy-mcp service
	@echo "🚀 Starting tidy-mcp service..."
	docker compose up -d --build tidy-mcp
	@echo "⏳ Waiting for tidy-mcp to be healthy..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health tidy-mcp --wait --timeout 30 || true
	@echo "✅ tidy-mcp service started!"

tidy-mcp-down: ## Stop tidy-mcp service
	@echo "🛑 Stopping tidy-mcp service..."
	docker compose stop tidy-mcp
	@echo "✅ tidy-mcp service stopped!"

tidy-mcp-restart: ## Restart tidy-mcp service
	@echo "🔄 Restarting tidy-mcp service..."
	docker compose restart tidy-mcp
	@echo "⏳ Waiting for tidy-mcp to be healthy..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health tidy-mcp --wait --timeout 30 || true
	@echo "✅ tidy-mcp service restarted!"

tidy-mcp-logs: ## View tidy-mcp service logs
	docker compose logs -f tidy-mcp

tidy-mcp-test: ## Test tidy-mcp HTTP endpoint
	@echo "🧪 Testing tidy-mcp HTTP endpoint..."
	@docker compose run --rm test curl -s -X POST "http://tidy-mcp:8000/tools/derive_xcallback_url_from_noteplan_file" \
		-H "Content-Type: application/json" \
		-d '{"file_path": "2025-11-13.md"}' \
		| ( command -v jq >/dev/null 2>&1 && jq . || cat )
	@echo "✅ tidy-mcp test completed!"

# =============================================================================
# DEVELOPMENT TARGETS
# =============================================================================

dev: build docker-up ## Development setup (build + start)
	@echo "✅ Development environment ready"

clean: docker-clean ## Clean everything
	rm -rf build/
	@echo "✅ Cleaned build artifacts"

# =============================================================================
# UTILITY TARGETS
# =============================================================================

dashboard: ## Generate simple dashboard
	python scripts/generate_simple_dashboard.py

open-dashboard: 
	python scripts/generate_simple_dashboard.py --open

canary-logs: ## View canary monitoring logs with debug output
	docker compose logs -f canary

canary-restart: ## Restart canary service with debug logging
	docker compose down canary
	docker compose up -d --build canary

wait-for-services: ## Wait for services to be ready
	@echo "⏳ Waiting for services to be ready..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health postgres qdrant llm-proxy --wait --timeout 60 || true

db-seed-database: wait-for-services ## Re-seed PostgreSQL container with Plans/Buckets/Tasks
	@echo "🔄 Re-seeding PostgreSQL database..."
	@echo "⚠️  NOTE: Only dropping our tables (plans, buckets, tasks), preserving LiteLLM tables..."
	docker compose exec postgres psql -U knowledge -d knowledge_workflow -c "DROP TABLE IF EXISTS tasks CASCADE; DROP TABLE IF EXISTS buckets CASCADE; DROP TABLE IF EXISTS plans CASCADE;"
	docker compose exec postgres psql -U knowledge -d knowledge_workflow -f /docker-entrypoint-initdb.d/01-init-db.sql
	@echo "✅ PostgreSQL database schema re-created successfully"
	@echo "🔄 Seeding database with Plans/Buckets/Tasks..."
	@docker compose --profile seeding run --rm seeder python scripts/seed_database.py
	@echo "✅ PostgreSQL database seeded successfully"

db-seed-vector-store: wait-for-services ## Seeding vector database from NotePlan files
	@echo "🔄 Re-seeding vector database ..."
	@docker compose --profile seeding run --rm seeder python scripts/seed_vector_store.py
	@echo "✅ Vector database seeded successfully"

db-seed: wait-for-services db-seed-database db-seed-vector-store ## Re-seed PostgreSQL container with Plans/Buckets/Tasks and vector database from NotePlan files

# =============================================================================
# NEO4J TARGETS
# =============================================================================

neo4j-seed-vector: wait-for-services ## Seed Neo4j vector store with note embeddings
	@echo "🔄 Seeding Neo4j vector store with note embeddings..."
	@docker compose run --rm -v $(PWD)/build:/app/build seeder python scripts/seed_neo4j_vector_store.py
	@echo "✅ Neo4j vector store seeded successfully"

neo4j-seed-graph: wait-for-services ## Seed Neo4j graph database with entities and relationships
	@echo "🔄 Seeding Neo4j graph database with entities and relationships..."
	@docker compose run --rm -v $(PWD)/build:/app/build seeder python scripts/seed_graph_database.py
	@echo "✅ Neo4j graph database seeded successfully"

neo4j-build-graph: wait-for-services ## Build Neo4j knowledge graph from notes (continuous builder)
	@echo "🔄 Building Neo4j knowledge graph from notes..."
	@docker compose run --rm -v $(PWD)/build:/app/build seeder python scripts/build_neo4j_graph.py
	@echo "✅ Neo4j knowledge graph built successfully"

neo4j-query: ## Query Neo4j graph interactively (usage: make neo4j-query QUERY="your question")
	@if [ -z "$(QUERY)" ]; then \
		echo "🔍 Starting interactive Neo4j graph query mode..."; \
		docker compose run --rm -v $(PWD)/build:/app/build seeder python scripts/query_neo4j_graph.py; \
	else \
		echo "🔍 Querying Neo4j graph: $(QUERY)"; \
		docker compose run --rm -v $(PWD)/build:/app/build seeder python scripts/query_neo4j_graph.py --question "$(QUERY)"; \
	fi

neo4j-graph-builder-up: ## Start Neo4j graph builder service
	@echo "🚀 Starting Neo4j graph builder service..."
	@docker compose up -d --build neo4j-graph-builder
	@echo "⏳ Waiting for Neo4j graph builder to start..."
	@sleep 5
	@echo "✅ Neo4j graph builder service started!"
	@echo "📋 View logs with: make neo4j-graph-builder-logs"

neo4j-graph-builder-down: ## Stop Neo4j graph builder service
	@echo "🛑 Stopping Neo4j graph builder service..."
	@docker compose stop neo4j-graph-builder
	@echo "✅ Neo4j graph builder service stopped!"

neo4j-graph-builder-restart: ## Restart Neo4j graph builder service
	@echo "🔄 Restarting Neo4j graph builder service..."
	@docker compose restart neo4j-graph-builder
	@echo "⏳ Waiting for Neo4j graph builder to restart..."
	@sleep 5
	@echo "✅ Neo4j graph builder service restarted!"

neo4j-graph-builder-logs: ## View Neo4j graph builder service logs
	@docker compose logs -f neo4j-graph-builder

neo4j-setup: wait-for-services neo4j-seed-vector neo4j-seed-graph ## Complete Neo4j setup (seed vector store + seed graph database)
	@echo "✅ Neo4j setup completed!"

db-reset: ## Reset PostgreSQL database completely (destroys all data)
	@echo "⚠️  Resetting PostgreSQL database (this will destroy all data)..."
	docker compose down postgres
	docker volume rm interview-omars-lab-8d8686a60ee646c5b774c3e1139a0c48_postgres_data || true
	docker compose up -d postgres
	@echo "⏳ Waiting for PostgreSQL to be ready..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health postgres --wait --timeout 30 || true
	@echo "✅ Database reset complete"

db-logs: ## View PostgreSQL database logs
	docker compose logs -f postgres

db-list-litellm-tokens: ## List all LiteLLM verification tokens from the database
	@echo "🔑 Listing LiteLLM verification tokens..."
	@docker compose exec -T postgres psql -U knowledge -d knowledge_workflow -c "SELECT token, key_name, key_alias, models, expires, user_id, team_id, blocked, spend, max_budget FROM \"LiteLLM_VerificationTokenView\" ORDER BY expires DESC NULLS LAST;" 2>/dev/null || \
	docker compose exec -T postgres psql -U knowledge -d knowledge_workflow -c "SELECT token, key_name, key_alias, models, expires, user_id, team_id, blocked, spend, max_budget FROM \"LiteLLM_VerificationToken\" ORDER BY expires DESC NULLS LAST;" 2>/dev/null || \
	(echo "⚠️  Could not find LiteLLM_VerificationToken table or view." && \
	 echo "   Make sure LiteLLM proxy has been started and initialized the database." && exit 1)

test-api: ## Test the note query API with curl (usage: make test-api QUERY="your question" API_KEY="your-token")
	@API_KEY_VALUE=$$($(PWD)/scripts/makefile-helper.sh get_api_key "$(API_KEY)"); \
	$(PWD)/scripts/makefile-helper.sh test_note_query_api "$(QUERY)" "$$API_KEY_VALUE"

litellm: ## Call LiteLLM via proxy (usage: make litellm PROMPT="text" MODEL="model" or EMBEDDING="text")
	@$(PWD)/scripts/call_litellm.sh \
		$(if $(PROMPT),--prompt "$(PROMPT)") \
		$(if $(EMBEDDING),--embedding "$(EMBEDDING)") \
		$(if $(MODEL),--model "$(MODEL)") \
		$(if $(PROXY_HOST),--proxy-host "$(PROXY_HOST)") \
		$(if $(PROXY_PORT),--proxy-port "$(PROXY_PORT)")

litellm-embedding: ## Run Qwen3 embedding model (usage: make litellm-embedding TEXT="text")
	@if [ -z "$(TEXT)" ]; then \
		echo "❌ Provide TEXT=\"text to embed\""; \
		exit 1; \
	fi
	@$(PWD)/scripts/call_litellm.sh --embedding "$(TEXT)" --model "lm_studio/text-embedding-qwen3-embedding-8b"

litellm-code: ## Run Qwen3 Coder model (usage: make litellm-code PROMPT="code prompt")
	@if [ -z "$(PROMPT)" ]; then \
		echo "❌ Provide PROMPT=\"your code prompt\""; \
		exit 1; \
	fi
	@$(PWD)/scripts/call_litellm.sh --prompt "$(PROMPT)" --model "lm_studio/qwen3-coder-30b"

litellm-generate-api-token: ## Generate API key via LiteLLM proxy and save to secrets file
	@$(PWD)/scripts/generate_litellm_api_key.sh

# =============================================================================
# WORKFLOW TARGETS
# =============================================================================

release: ## Comprehensive release readiness checks
	@echo "🔍 Running release checks..."
	@make format
	@make lint
	@make type-check
	@make test
	@echo "✅ Release checks passed - code is ready for release!"

sample-test: ## Run sample tests for quick verification
	@echo "🧪 Running sample tests with proper logging..."
	@echo "📋 Checking service status..."
	@SERVICES="postgres agentic-api"; \
	$(PWD)/scripts/makefile-helper.sh check_service_health $$SERVICES 2>/dev/null; \
	EXIT_CODE=$$?; \
	if [ $$EXIT_CODE -eq 2 ]; then \
		echo "⏳ Building and starting full stack..."; \
		docker compose up -d --build postgres prometheus agentic-api test; \
	fi
	@echo "⏳ Waiting for services to be healthy..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health postgres agentic-api --wait --timeout 30 || true
	@echo "🔎 Running sample unit test..."
	docker compose exec -T test pytest tst/unit/test_config.py::TestConfigLoading::test_config_loading_defaults -v -s --log-cli-level=DEBUG
	@echo "🔎 Running sample integration test..."
	docker compose exec -T test pytest tst/integration/api/test_agentic_api_happy_path.py::TestAgenticAPIHappyPathScenarios::test_complete_api_endpoint_integration -v -s --log-cli-level=DEBUG
	@echo "✅ Sample tests completed successfully!"

feedback-loop: sample-test ## Run feedback loop (sample-test alias)

# =============================================================================
# SINGLE TEST TARGETS
# =============================================================================

test-one: ## Run single test (usage: make test-one TEST=path/to/test)
	@if [ -z "$(TEST)" ]; then echo "❌ Please provide TEST=<path>"; exit 1; fi
	docker compose run --rm -v $(PWD)/build:/app/build test pytest $(TEST) -v

unit-test-one: ## Run single unit test (usage: make unit-test-one TEST=path/to/test) - Uses conda environment
	@if [ -z "$(TEST)" ]; then echo "❌ Please provide TEST=<path>"; exit 1; fi
	@if ! conda env list | grep -q "^$(conda-env-name) "; then \
		echo "❌ Conda environment '$(conda-env-name)' not found. Run 'make conda-setup' first."; \
		exit 1; \
	fi
	@conda run -n $(conda-env-name) pytest $(TEST) -v -m "unit"

integration-test-one: ## Run single integration test (usage: make integration-test-one TEST=path/to/test)
	@if [ -z "$(TEST)" ]; then echo "❌ Please provide TEST=<path>"; exit 1; fi
	docker compose run --rm -v $(PWD)/build:/app/build -v $(PWD)/tst:/app/tst -v $(PWD)/src:/app/src test pytest $(TEST) -v -m "integration" --log-cli-level=DEBUG

# =============================================================================
# END-TO-END TEST TARGETS (OPTIMIZED FOR FAST FEEDBACK LOOP)
# =============================================================================
# 
# FAST FEEDBACK LOOP STRATEGY:
#   1. Run `make test-note-query-prepare` once to set up services and seed data
#   2. Run `make test-note-query-validate` repeatedly for fast iteration
#   3. Run `make test-note-query-e2e-fast` for a quick check (skips seeding if data exists)
#   4. Run `make test-note-query-e2e-full` when you need a full reset (slow but comprehensive)
#
# RECOMMENDED WORKFLOW:
#   - First time: `make test-note-query-prepare` (takes 2-5 minutes)
#   - During development: `make test-note-query-validate` (takes 10-30 seconds)
#   - Before committing: `make test-note-query-e2e-fast` (takes 1-2 minutes)
#   - After schema changes: `make test-note-query-e2e-full` (takes 2-5 minutes)

test-note-query-prepare: ## Prepare test environment (services + seeding) - Run once, then use test-note-query-validate
	@echo "🏗️  Preparing test environment..."
	@echo "⏳ Checking service status..."
	@SERVICES="postgres qdrant llm-proxy agentic-api"; \
	$(PWD)/scripts/makefile-helper.sh check_service_health $$SERVICES 2>/dev/null; \
	EXIT_CODE=$$?; \
	if [ $$EXIT_CODE -eq 2 ]; then \
		echo "⏳ Starting required services..."; \
		docker compose up -d $$SERVICES; \
	fi
	@echo "⏳ Waiting for services to be healthy..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health postgres qdrant llm-proxy agentic-api --wait --timeout 60 || true
	@echo "🔄 Restarting LiteLLM proxy to ensure database tables are initialized..."
	@docker compose restart llm-proxy
	@echo "⏳ Waiting for LiteLLM proxy to be healthy after restart..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health llm-proxy --wait --timeout 30 || true
	@echo "🔄 Seeding database and vector store..."
	@make db-seed || true
	@echo "✅ Test environment prepared! Run 'make test-note-query-validate' to run tests."

test-note-query-validate: ## Run tests only (assumes environment is prepared) - FAST ITERATION
	@echo "🔎 Running note query integration tests (validation only)..."
	@echo "⏳ Verifying services are healthy..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health postgres qdrant llm-proxy agentic-api --wait --timeout 30 || { \
		echo "❌ Services not healthy. Run 'make test-note-query-prepare' first."; \
		exit 1; \
	}
	@echo "🔎 Running note query agent integration tests..."
	@docker compose run --rm -v $(PWD)/build:/app/build -v $(PWD)/tst:/app/tst -v $(PWD)/src:/app/src test pytest tst/integration/agents/test_note_query_agent.py -v -m "integration" --log-cli-level=INFO
	@echo "🔎 Running note query API integration tests..."
	@docker compose run --rm -v $(PWD)/build:/app/build -v $(PWD)/tst:/app/tst -v $(PWD)/src:/app/src test pytest tst/integration/api/test_note_query_api.py -v -m "integration" --log-cli-level=INFO
	@echo "✅ Validation completed!"

test-note-query-e2e-fast: ## Fast e2e test (skips seeding if data exists) - RECOMMENDED for quick feedback
	@echo "⚡ Running fast end-to-end test (skips seeding if data exists)..."
	@echo "⏳ Checking service status..."
	@SERVICES="postgres qdrant llm-proxy agentic-api"; \
	$(PWD)/scripts/makefile-helper.sh check_service_health $$SERVICES 2>/dev/null; \
	EXIT_CODE=$$?; \
	if [ $$EXIT_CODE -eq 2 ]; then \
		echo "⏳ Starting required services..."; \
		docker compose up -d $$SERVICES; \
	fi
	@echo "⏳ Waiting for services to be healthy..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health postgres qdrant llm-proxy agentic-api --wait --timeout 60 || true
	@echo "🔄 Restarting LiteLLM proxy to ensure database tables are initialized..."
	@docker compose restart llm-proxy
	@echo "⏳ Waiting for LiteLLM proxy to be healthy after restart..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health llm-proxy --wait --timeout 30 || true
	@echo "⏳ Checking if data already exists..."
	@if ! $(PWD)/scripts/makefile-helper.sh check_data_exists 2>/dev/null; then \
		echo "🔄 Data not found, seeding database and vector store..."; \
		make db-seed || true; \
	else \
		echo "✅ Data already exists, skipping seeding..."; \
	fi
	@echo "🔎 Running note query agent integration tests..."
	@docker compose run --rm -v $(PWD)/build:/app/build -v $(PWD)/tst:/app/tst -v $(PWD)/src:/app/src test pytest tst/integration/agents/test_note_query_agent.py -v -m "integration" --log-cli-level=INFO
	@echo "🔎 Running note query API integration tests..."
	@docker compose run --rm -v $(PWD)/build:/app/build -v $(PWD)/tst:/app/tst -v $(PWD)/src:/app/src test pytest tst/integration/api/test_note_query_api.py -v -m "integration" --log-cli-level=INFO
	@echo "✅ Fast end-to-end test completed!"

test-note-query-e2e-full: ## Full e2e test (always re-seeds) - Use after schema changes or when you need a clean slate
	@echo "🔄 Running full end-to-end test (always re-seeds)..."
	@echo "⏳ Checking service status..."
	@SERVICES="postgres qdrant llm-proxy agentic-api"; \
	$(PWD)/scripts/makefile-helper.sh check_service_health $$SERVICES 2>/dev/null; \
	EXIT_CODE=$$?; \
	if [ $$EXIT_CODE -eq 2 ]; then \
		echo "⏳ Starting required services..."; \
		docker compose up -d $$SERVICES; \
	fi
	@echo "⏳ Waiting for services to be healthy..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health postgres qdrant llm-proxy agentic-api --wait --timeout 60 || true
	@echo "🔄 Restarting LiteLLM proxy to ensure database tables are initialized..."
	@docker compose restart llm-proxy
	@echo "⏳ Waiting for LiteLLM proxy to be healthy after restart..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health llm-proxy --wait --timeout 30 || true
	@echo "🔄 Re-seeding database and vector store (full reset)..."
	@make db-seed || true
	@echo "🔎 Running note query agent integration tests..."
	@docker compose run --rm -v $(PWD)/build:/app/build -v $(PWD)/tst:/app/tst -v $(PWD)/src:/app/src test pytest tst/integration/agents/test_note_query_agent.py -v -m "integration" --log-cli-level=INFO
	@echo "🔎 Running note query API integration tests..."
	@docker compose run --rm -v $(PWD)/build:/app/build -v $(PWD)/tst:/app/tst -v $(PWD)/src:/app/src test pytest tst/integration/api/test_note_query_api.py -v -m "integration" --log-cli-level=INFO
	@echo "✅ Full end-to-end test completed!"

test-note-query-e2e: test-note-query-e2e-fast ## Alias for fast e2e test (backward compatibility)

test-tools: ## Run integration tests for tools (tidy-mcp, NotePlan tools)
	@echo "🧪 Running tools integration tests..."
	@if ! $(PWD)/scripts/makefile-helper.sh check_service_health tidy-mcp 2>/dev/null; then \
		echo "⚠️  tidy-mcp service not running. Starting it..."; \
		make tidy-mcxp-up; \
	fi
	@echo "⏳ Waiting for tidy-mcp to be healthy..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health tidy-mcp --wait --timeout 30 || true
	@docker compose exec -T test pytest tst/integration/tools/ -v --tb=short
	@echo "✅ Tools integration tests completed!"

test-note-query-api: ## Quick test of note query API endpoint (usage: make test-note-query-api QUERY="your question" API_KEY="your-token")
	@if [ -z "$(QUERY)" ]; then echo "❌ Please provide QUERY=\"your question\""; exit 1; fi
	@if [ -z "$(API_KEY)" ]; then \
		if [ -f secrets/openai_api_key.txt ]; then \
			API_KEY=$$(cat secrets/openai_api_key.txt | tr -d '\n'); \
		else \
			echo "❌ Please provide API_KEY=\"your-token\" or ensure secrets/openai_api_key.txt exists"; \
			exit 1; \
		fi; \
	fi
	@echo "🧪 Testing note query API with query: $(QUERY)"
	@docker compose run --rm test curl -s -X POST "http://agentic-api:8000/api/v1/notes/query" \
		-H "Content-Type: application/json" \
		-H "Authorization: Bearer $$API_KEY" \
		-d "{\"query\": \"$(QUERY)\"}" \
		| ( command -v jq >/dev/null 2>&1 && jq . || cat )

# =============================================================================
# CLAUDE AGENT TARGETS
# =============================================================================

refresh-env: ## Refresh .env file with credentials from macOS Keychain + environment
	@echo "🔑 Refreshing .env credentials..."
	@touch .env; \
	_update_env_key() { \
		local key=$$1 val=$$2; \
		if grep -q "^$$key=" .env 2>/dev/null; then \
			sed -i '' "s|^$$key=.*|$$key=$$val|" .env; \
		else \
			echo "$$key=$$val" >> .env; \
		fi; \
	}; \
	ANTHROPIC_KEY=""; \
	if [ -n "$$ANTHROPIC_API_KEY" ]; then \
		ANTHROPIC_KEY="$$ANTHROPIC_API_KEY"; \
		echo "  ✅ ANTHROPIC_API_KEY from environment ($${#ANTHROPIC_KEY} chars)"; \
	else \
		ANTHROPIC_KEY=$$(security find-generic-password -a "ANTHROPIC_API_KEY" -w 2>/dev/null || true); \
		if [ -n "$$ANTHROPIC_KEY" ] && [ "$${#ANTHROPIC_KEY}" -gt 20 ]; then \
			echo "  ✅ ANTHROPIC_API_KEY from Keychain ($${#ANTHROPIC_KEY} chars)"; \
		else \
			ANTHROPIC_KEY=""; \
			echo "  ⚠️  No ANTHROPIC_API_KEY found."; \
			echo "     Set env var:  export ANTHROPIC_API_KEY=sk-ant-..."; \
			echo "     Or Keychain:  security add-generic-password -a ANTHROPIC_API_KEY -s knowledge-agents -w 'sk-ant-...'"; \
		fi; \
	fi; \
	if [ -n "$$ANTHROPIC_KEY" ]; then \
		if grep -q "^ANTHROPIC_API_KEY=" .env 2>/dev/null; then \
			sed -i '' "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$$ANTHROPIC_KEY|" .env; \
		else \
			echo "ANTHROPIC_API_KEY=$$ANTHROPIC_KEY" >> .env; \
		fi; \
	fi

claude-agent-up: refresh-env ## Start Claude Agent service and its dependencies
	@echo "🚀 Starting Claude Agent service..."
	docker compose up -d --build claude-agent
	@echo "⏳ Waiting for Claude Agent to be healthy..."
	@$(PWD)/scripts/makefile-helper.sh check_service_health claude-agent --wait --timeout 60 || true
	@echo "✅ Claude Agent service started on port 8004"

claude-agent-login: ## Interactive login for Claude CLI inside the container (persists in volume)
	@echo "🔐 Starting Claude CLI login inside container..."
	@echo "   This opens a browser URL — follow the prompts to authenticate."
	@echo "   Auth is stored in the 'claude_agent_config' Docker volume and persists across restarts."
	@echo ""
	docker exec -it knowledge-agents-claude-agent-1 claude auth login --claudeai
	@echo ""
	@echo "✅ Login complete. Checking auth status..."
	@$(MAKE) claude-agent-auth-status

claude-agent-auth-seed: ## Seed container auth from host macOS Keychain (no interactive login needed)
	@echo "🔑 Seeding container Claude auth from host Keychain..."
	@CREDS=$$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null); \
	if [ -z "$$CREDS" ] || [ "$${#CREDS}" -lt 50 ]; then \
		echo "❌ No valid credentials in Keychain (service='Claude Code-credentials')"; \
		echo "   Run 'claude auth login' on the host first, then retry."; \
		exit 1; \
	fi; \
	echo "$$CREDS" | docker exec -i knowledge-agents-claude-agent-1 bash -c \
		'mkdir -p /home/agent/.claude && cat > /home/agent/.claude/.credentials.json && chmod 600 /home/agent/.claude/.credentials.json && echo "✅ Credentials seeded to container volume (.credentials.json)"'
	@$(MAKE) claude-agent-auth-status

claude-agent-auth-status: ## Check Claude CLI auth status + credential expiry in container
	@echo "🔍 Claude CLI auth status:"
	@AUTH_JSON=$$(docker exec knowledge-agents-claude-agent-1 claude auth status --json 2>/dev/null); \
	if [ -n "$$AUTH_JSON" ]; then \
		echo "$$AUTH_JSON" | python3 -m json.tool 2>/dev/null || echo "$$AUTH_JSON"; \
		echo ""; \
	else \
		echo "❌ Not authenticated — run 'make claude-agent-login' or 'make claude-agent-auth-seed'"; \
	fi
	@echo "⏰ Token expiry check:"
	@docker cp scripts/check_claude_auth_expiry.py knowledge-agents-claude-agent-1:/tmp/check_expiry.py 2>/dev/null; \
	docker exec knowledge-agents-claude-agent-1 python3 /tmp/check_expiry.py 2>&1 || echo "  Could not check expiry"
	@echo ""
	@echo "🔄 To refresh: make claude-agent-login  |  make claude-agent-auth-seed"

claude-agent-down: ## Stop Claude Agent service
	@echo "🛑 Stopping Claude Agent service..."
	docker compose stop claude-agent
	@echo "✅ Claude Agent service stopped"

claude-agent-logs: ## View Claude Agent service logs
	docker compose logs -f claude-agent

claude-agent-test: ## Run Claude Agent unit tests
	@echo "🧪 Running Claude Agent unit tests..."
	@if ! conda env list | grep -q "^$(conda-env-name) "; then \
		echo "❌ Conda environment '$(conda-env-name)' not found. Run 'make conda-setup' first."; \
		exit 1; \
	fi
	@conda run -n $(conda-env-name) pytest tst/unit/claude_agent/ -v -m "unit" --tb=short
	@echo "✅ Claude Agent unit tests completed"

claude-agent-integration-test: ## Run Claude Agent integration tests (requires running services)
	@echo "🧪 Running Claude Agent integration tests..."
	docker compose run --rm -v $(PWD)/build:/app/build -v $(PWD)/tst:/app/tst -v $(PWD)/src:/app/src test pytest tst/integration/claude_agent/ -v -m "claude_agent" --log-cli-level=INFO
	@echo "✅ Claude Agent integration tests completed"

claude-agent-eval: ## Run full Claude Agent eval suite
	@echo "📊 Running Claude Agent eval suite..."
	@conda run -n $(conda-env-name) python -m evals.claude_agent.runner
	@echo "✅ Eval suite completed"

claude-agent-eval-search: ## Run only search evals
	@echo "📊 Running search evals..."
	@conda run -n $(conda-env-name) python -m evals.claude_agent.runner --dataset note_search
	@echo "✅ Search evals completed"

claude-agent-eval-graph: ## Run only graph evals
	@echo "📊 Running graph evals..."
	@conda run -n $(conda-env-name) python -m evals.claude_agent.runner --dataset graph_building
	@echo "✅ Graph evals completed"

claude-agent-eval-report: ## Generate eval report from latest results
	@echo "📊 Generating eval report..."
	@conda run -n $(conda-env-name) python -m evals.claude_agent.report
	@echo "✅ Eval report generated"

claude-agent-clean-sessions: ## Clean up old session workspaces
	@echo "🧹 Cleaning old session workspaces..."
	@rm -rf build/sessions/*
	@echo "✅ Session workspaces cleaned"

LMS_SSH_HOST ?= mac-studio

lm-studio-status: ## Check LM Studio status (local or remote via LMS_SSH_HOST)
	@./scripts/lm_studio_ctl.sh status --remote $(LMS_SSH_HOST)

lm-studio-status-local: ## Check LM Studio status (local machine)
	@./scripts/lm_studio_ctl.sh status

lm-studio-load-embeddings: ## Load the embedding model (remote via LMS_SSH_HOST)
	@./scripts/lm_studio_ctl.sh load-embeddings --remote $(LMS_SSH_HOST)

lm-studio-test-embedding: ## Test embedding generation end-to-end
	@./scripts/lm_studio_ctl.sh test-embedding --remote $(LMS_SSH_HOST)

lm-studio-ls: ## List all downloaded models
	@./scripts/lm_studio_ctl.sh ls --remote $(LMS_SSH_HOST)

claude-agent-chat: ## Quick test of Claude Agent chat (usage: make claude-agent-chat MSG="your question")
	@if [ -z "$(MSG)" ]; then echo "❌ Please provide MSG=\"your question\""; exit 1; fi
	@echo "💬 Sending message to Claude Agent: $(MSG)"
	@curl -s -X POST "http://localhost:8004/api/v1/chat" \
		-H "Content-Type: application/json" \
		-d "{\"message\": \"$(MSG)\"}" \
		| ( command -v jq >/dev/null 2>&1 && jq . || cat )

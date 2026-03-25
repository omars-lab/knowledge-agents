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

.PHONY: help start build test clean format lint type-check docker-up docker-down litellm litellm-embedding litellm-code tidy-mcp-up tidy-mcp-down tidy-mcp-restart tidy-mcp-logs tidy-mcp-test test-tools neo4j-seed-vector neo4j-seed-graph neo4j-build-graph neo4j-query neo4j-graph-builder-up neo4j-graph-builder-down neo4j-graph-builder-restart neo4j-graph-builder-logs claude-agent-up claude-agent-down claude-agent-logs claude-agent-test claude-agent-eval claude-agent-clean-sessions local-deploy deploy deploy-status deploy-down deploy-logs verify

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

EVAL_DOCKER = docker compose run --rm \
	-e AGENT_BASE_URL=http://claude-agent:8000 \
	-e PYTHONPATH=/app \
	test

claude-agent-eval: ## Run full Claude Agent eval suite (in Docker, works locally or on Mac Studio)
	@echo "📊 Running Claude Agent eval suite..."
	@$(call run,$(EVAL_DOCKER) python -m evals.claude_agent.runner)
	@echo "✅ Eval suite completed"

claude-agent-eval-search: ## Run only search evals
	@echo "📊 Running search evals..."
	@$(call run,$(EVAL_DOCKER) python -m evals.claude_agent.runner --dataset note_search)
	@echo "✅ Search evals completed"

claude-agent-eval-graph: ## Run only graph evals
	@echo "📊 Running graph evals..."
	@$(call run,$(EVAL_DOCKER) python -m evals.claude_agent.runner --dataset graph_building)
	@echo "✅ Graph evals completed"

claude-agent-eval-report: ## Generate eval report from latest results
	@echo "📊 Generating eval report..."
	@$(call run,$(EVAL_DOCKER) python -m evals.claude_agent.report)
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

claude-agent-graph: ## Render knowledge graph as SVG (usage: make claude-agent-graph QUERY="entity name" or CYPHER="match query")
	@mkdir -p build/graphs
	@if [ -n "$(ENTITY)" ]; then \
		conda run -n $(conda-env-name) python scripts/render_graph.py --entity "$(ENTITY)" --output build/graphs/latest.svg; \
	elif [ -n "$(CYPHER)" ]; then \
		conda run -n $(conda-env-name) python scripts/render_graph.py --query "$(CYPHER)" --output build/graphs/latest.svg; \
	else \
		conda run -n $(conda-env-name) python scripts/render_graph.py --all --output build/graphs/latest.svg; \
	fi
	@echo "📊 Opening graph..."
	@open build/graphs/latest.svg 2>/dev/null || echo "  Open: build/graphs/latest.svg"

NOTEPLAN_DIR ?= /Users/omareid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3

seed-sections: ## Index NotePlan sections into Qdrant + Neo4j (delta — only changed files)
	@conda run -n $(conda-env-name) python scripts/seed_sections.py \
		--noteplan-dir "$(NOTEPLAN_DIR)" --delay 0.5

seed-sections-full: ## Full re-index all NotePlan sections
	@conda run -n $(conda-env-name) python scripts/seed_sections.py \
		--noteplan-dir "$(NOTEPLAN_DIR)" --full-reindex --delay 0.5

seed-sections-summarize: ## Index sections with LLM summarization
	@conda run -n $(conda-env-name) python scripts/seed_sections.py \
		--noteplan-dir "$(NOTEPLAN_DIR)" --summarize --concurrency 3 --delay 1

claude-agent-chat: ## Quick test of Claude Agent chat (usage: make claude-agent-chat MSG="your question")
claude-agent-changelog: ## Render temporal knowledge graph (usage: make claude-agent-changelog START=2026-03-17 END=2026-03-24)
	@if [ -z "$(START)" ] || [ -z "$(END)" ]; then echo "❌ Usage: make claude-agent-changelog START=YYYY-MM-DD END=YYYY-MM-DD"; exit 1; fi
	@conda run -n $(conda-env-name) python scripts/render_temporal_graph.py \
		--start "$(START)" --end "$(END)" --output build/graphs/changelog.svg
	@echo "📊 Opening changelog graph..."
	@open build/graphs/changelog.svg 2>/dev/null || echo "  Open: build/graphs/changelog.svg"

claude-agent-chat: ## Quick test of Claude Agent chat (usage: make claude-agent-chat MSG="your question")
	@if [ -z "$(MSG)" ]; then echo "❌ Please provide MSG=\"your question\""; exit 1; fi
	@echo "💬 Sending message to Claude Agent: $(MSG)"
	@curl -s -X POST "http://localhost:8004/api/v1/chat" \
		-H "Content-Type: application/json" \
		-d "{\"message\": \"$(MSG)\"}" \
		| ( command -v jq >/dev/null 2>&1 && jq . || cat )

# =============================================================================
# OBSERVABILITY TARGETS
# =============================================================================

observability-install: ## Install Loki Docker logging driver plugin (one-time)
	@echo "🔌 Installing Loki Docker logging driver..."
	@docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions 2>/dev/null \
		&& echo "✅ Installed locally" || echo "ℹ️  Already installed locally (or error)"
	@echo "🔍 Verifying:"
	@docker plugin ls | grep loki || echo "❌ Plugin not found"

observability-up: ## Start Grafana + Loki observability stack
	@echo "📊 Starting observability stack..."
	docker compose up -d loki grafana
	@echo "⏳ Waiting for Loki..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		curl -sf http://localhost:3100/ready >/dev/null 2>&1 && echo "✅ Loki ready" && break || sleep 2; \
	done
	@echo "✅ Grafana: http://localhost:3001 (admin/knowledge123)"

observability-down: ## Stop observability stack
	@echo "🛑 Stopping observability stack..."
	docker compose stop grafana loki
	@echo "✅ Stopped"

grafana-open: ## Open Grafana dashboard in browser
	@open http://localhost:3001 2>/dev/null || echo "Open: http://localhost:3001"

model-eval: ## Run model config eval sweep (all configs × all test cases)
	@conda run -n $(conda-env-name) python -m evals.model_config.runner --delay 2

model-eval-config: ## Run eval for a specific config (usage: make model-eval-config CONFIG="35b-a3b-t0.5")
	@conda run -n $(conda-env-name) python -m evals.model_config.runner --config "$(CONFIG)" --delay 2

model-eval-report: ## Generate comparison report from latest eval results
	@conda run -n $(conda-env-name) python -m evals.model_config.report

langfuse-up: ## Start Langfuse v3 LLM observability (ClickHouse + Redis + Minio + Worker + Web)
	@echo "🔍 Starting Langfuse v3 stack..."
	@docker compose up -d langfuse-clickhouse langfuse-redis langfuse-minio langfuse-create-bucket langfuse-worker langfuse
	@echo "⏳ Waiting for Langfuse to be healthy (may take 60-90s on first start)..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18; do \
		curl -sf http://localhost:3210/api/public/health >/dev/null 2>&1 && echo "✅ Langfuse: http://localhost:3210 (admin@local / knowledge123)" && break || sleep 5; \
	done

langfuse-down: ## Stop Langfuse stack
	docker compose stop langfuse langfuse-worker langfuse-clickhouse langfuse-redis langfuse-minio

langfuse-open: ## Open Langfuse UI in browser
	@open http://localhost:3210 2>/dev/null || echo "Open: http://localhost:3210"

# =============================================================================
# DEPLOY TARGETS
# =============================================================================
#
# Git-based deploy. Detects whether running on Mac Studio (local) or remote.
#   Local (Mac Studio):  git pull + build + start — no SSH needed.
#   Remote (MacBook):    push + SSH to Mac Studio, then same steps.
# Never use rsync — all changes must go through git.
#
# On Mac Studio, LM_STUDIO_HOST is set to localhost (LM Studio runs there).

STUDIO_HOST ?= mac-studio
STUDIO_PATH ?= ~/Workspace/git/knowledge-agents

# ── Host detection ────────────────────────────────────────────────────────────
# Reuse hosts.yml if it exists (same pattern as private-site), otherwise
# fall back to hostname-based detection.
IS_STUDIO := $(shell \
	if [ -f hosts.yml ]; then \
		MY_SERIAL=$$(system_profiler SPHardwareDataType 2>/dev/null | awk '/Serial Number/ {print $$NF}'); \
		grep -q "$$MY_SERIAL" hosts.yml 2>/dev/null && \
		awk "/$$MY_SERIAL/,/role/" hosts.yml | grep -q 'role: prod' && echo true || echo false; \
	else \
		hostname | grep -qi "mac-studio" && echo true || echo false; \
	fi)

# Helper: run a command locally or via SSH depending on IS_STUDIO
run = $(if $(filter true,$(IS_STUDIO)),cd $(STUDIO_PATH) && $(1),ssh $(STUDIO_HOST) "zsh -l -c 'cd $(STUDIO_PATH) && $(1)'")

.PHONY: local-deploy deploy deploy-status deploy-down deploy-logs

local-deploy: ## Deploy stack locally (LM_STUDIO_HOST=localhost)
	@echo "── Deploying locally (LM_STUDIO_HOST=localhost) ──"
	LM_STUDIO_HOST=localhost $(MAKE) start
	@echo ""
	@echo "✓ Local deploy complete — API at http://localhost:8004"

deploy: ## Deploy to Mac Studio (or locally if already on Mac Studio)
	@echo "── Pre-flight: git status ──"
	@if [ -n "$$(git status -s --ignore-submodules)" ]; then \
		echo "✗ Uncommitted changes — commit and push first"; \
		git status -s; \
		exit 1; \
	fi
	@LOCAL_BRANCH=$$(git rev-parse --abbrev-ref HEAD) && \
	 LOCAL_SHA=$$(git rev-parse HEAD) && \
	 REMOTE_SHA=$$(git rev-parse origin/$$LOCAL_BRANCH 2>/dev/null || echo "none") && \
	 if [ "$$LOCAL_SHA" != "$$REMOTE_SHA" ]; then \
		echo "✗ Branch '$$LOCAL_BRANCH' not pushed — run: git push"; \
		exit 1; \
	 fi && \
	 echo "✓ Branch '$$LOCAL_BRANCH' in sync with origin ($$LOCAL_SHA)"
	@echo ""
	@if [ "$(IS_STUDIO)" = "true" ]; then \
		echo "── Detected: running on Mac Studio (local deploy) ──"; \
	else \
		echo "── Detected: remote machine → deploying via SSH to $(STUDIO_HOST) ──"; \
		ssh -o ConnectTimeout=5 $(STUDIO_HOST) "echo '✓ SSH OK'" || { echo "✗ Cannot reach $(STUDIO_HOST)"; exit 1; }; \
	fi
	@echo ""
	@echo "── Pulling latest ──"
	@$(call run,git fetch origin && git checkout $$(git rev-parse --abbrev-ref HEAD) && git pull origin $$(git rev-parse --abbrev-ref HEAD))
	@echo ""
	@echo "── Building + starting stack (LM_STUDIO_HOST=localhost) ──"
	@$(call run,LM_STUDIO_HOST=localhost make start)
	@echo ""
	@echo "── Post-deploy: container status ──"
	@$(call run,docker compose ps --format 'table {{.Name}}\t{{.Status}}')
	@echo ""
	@echo "── Post-deploy: cross-network connections ──"
	@$(call run,make cross-network-connect)
	@echo ""
	@echo "✓ Deploy complete ($(if $(filter true,$(IS_STUDIO)),local,via SSH to $(STUDIO_HOST))) — API at http://$(STUDIO_HOST):8004"

deploy-status: ## Check container status on Mac Studio
	@$(call run,docker compose ps)

deploy-down: ## Stop stack on Mac Studio
	@$(call run,docker compose down)

deploy-logs: ## Tail logs on Mac Studio
	@$(call run,docker compose logs -f --tail 50)

# ── Verify deployment ────────────────────────────────────────────────────────
# Post-deploy verification: checks all services via internal endpoints + SSH.
# Can run from any machine with SSH access to the Mac Studio.

.PHONY: verify

verify: ## Verify deployment — health checks for all services (runs on target host)
	@$(call run,bash scripts/verify.sh)


# =============================================================================
# SECURITY
# =============================================================================

check-ootb-secrets: ## Check that no OOTB/default credentials are in use
	@bash scripts/check-ootb-secrets.sh

# =============================================================================
# CROSS-STACK NETWORKING (private-site integration)
# =============================================================================

langfuse-connect: ## Connect Langfuse to private-site_internal network (for Kong routing)
	@docker network connect --alias langfuse private-site_internal knowledge-agents-langfuse-1 2>/dev/null && echo "✅ Langfuse connected to private-site_internal" || echo "⚠️  Already connected (or container not running)"

langfuse-disconnect: ## Disconnect Langfuse from private-site_internal network
	@docker network disconnect private-site_internal knowledge-agents-langfuse-1 2>/dev/null && echo "✅ Langfuse disconnected" || echo "⚠️  Not connected"

langfuse-check: ## Verify Langfuse is reachable from private-site network
	@docker exec private-site-mcp-1 python3 -c "import urllib.request; print(urllib.request.urlopen('http://langfuse:3000/api/public/health').read().decode())" 2>/dev/null && echo "✅ Langfuse reachable from private-site" || echo "❌ Langfuse NOT reachable — run: make langfuse-connect"

chat-connect: ## Connect chat UI to private-site_internal network (for Kong routing)
	@docker network connect --alias chat private-site_internal knowledge-agents-chat-1 2>/dev/null && echo "✅ Chat connected to private-site_internal" || echo "⚠️  Already connected (or container not running)"

chat-disconnect: ## Disconnect chat UI from private-site_internal network
	@docker network disconnect private-site_internal knowledge-agents-chat-1 2>/dev/null && echo "✅ Chat disconnected" || echo "⚠️  Not connected"

chat-check: ## Verify chat UI is reachable from private-site network
	@docker exec private-site-kong-1 wget -q --spider http://chat:80/health 2>/dev/null && echo "✅ Chat reachable from private-site" || echo "❌ Chat NOT reachable — run: make chat-connect"

claude-agent-connect: ## Connect claude-agent to private-site_internal network (for Kong routing)
	@docker network connect --alias claude-agent private-site_internal knowledge-agents-claude-agent-1 2>/dev/null && echo "✅ Claude-agent connected to private-site_internal" || echo "⚠️  Already connected (or container not running)"

claude-agent-disconnect: ## Disconnect claude-agent from private-site_internal network
	@docker network disconnect private-site_internal knowledge-agents-claude-agent-1 2>/dev/null && echo "✅ Claude-agent disconnected" || echo "⚠️  Not connected"

claude-agent-check: ## Verify claude-agent is reachable from private-site network
	@docker exec private-site-kong-1 wget -q --spider http://claude-agent:8000/health 2>/dev/null && echo "✅ Claude-agent reachable from private-site" || echo "❌ Claude-agent NOT reachable — run: make claude-agent-connect"

cross-network-connect: ## Connect all services to private-site_internal network
	@$(MAKE) langfuse-connect
	@$(MAKE) chat-connect
	@$(MAKE) claude-agent-connect

cross-network-check: ## Verify all services reachable from private-site network
	@$(MAKE) langfuse-check
	@$(MAKE) chat-check
	@$(MAKE) claude-agent-check

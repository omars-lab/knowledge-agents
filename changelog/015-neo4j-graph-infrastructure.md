---
commit: TBD
date: 2025-11-20
type: Added
---

# Neo4j Graph Infrastructure

## Description

Added comprehensive Neo4j integration for building and querying knowledge graphs from NotePlan notes. This includes graph database seeding, entity/relationship extraction using LLM agents, vector store integration, and Docker-based graph builder service.

## Changes

### Core Infrastructure
- **Neo4j Client Manager** (`src/knowledge_agents/clients/neo4j_client.py`): New client manager for Neo4j database connections with automatic vector index creation
- **Graph Types** (`src/knowledge_agents/types/graph.py`): Pydantic models for `Entity`, `Relationship`, and `GraphBuilderAgentOutput` with strict JSON schema enforcement
- **Graph Builder Agent** (`src/knowledge_agents/agents/graph_builder_agent.py`): LLM-powered agent for extracting entities and relationships from note content
- **Graph Builder Prompts** (`src/knowledge_agents/prompts/graph_builder_agent.py`): Specialized prompts for entity/relationship extraction

### Seeding Scripts
- **Neo4j Vector Store Seeding** (`scripts/seed_neo4j_vector_store.py`): Script to seed Neo4j vector store with NotePlan file embeddings using LiteLLM proxy
- **Graph Database Seeding** (`scripts/seed_graph_database.py`): Script to seed Neo4j graph with entities, relationships, and indexes from NotePlan files
- **Graph Builder** (`scripts/build_neo4j_graph.py`): Continuous graph builder service that processes notes and updates the knowledge graph

### Configuration & Dependencies
- **Neo4j Settings** (`src/knowledge_agents/config/api_config.py`): Added Neo4j connection settings (URI, credentials, database, index names)
- **Dependencies** (`src/knowledge_agents/dependencies.py`): Added `Neo4jClientManager` to dependency injection container
- **Graph Builder Requirements** (`requirements-graph-builder.txt`): New requirements file for graph-builder Docker service with Neo4j, LangChain, and graph data science libraries

### Docker & Infrastructure
- **Docker Compose** (`docker-compose.yml`): Added `neo4j-graph-builder` service with volume mounts for live code updates
- **Dockerfile** (`Dockerfile`): Added `graph-builder` stage with graph-specific dependencies
- **Volume Mounts**: Configured `src` and `scripts` directory mounts in both `seeder` and `neo4j-graph-builder` services for development workflow

### Makefile Targets
- `neo4j-seed-vector`: Seed Neo4j vector store with note embeddings
- `neo4j-seed-graph`: Seed Neo4j graph database with entities and relationships
- `neo4j-build-graph`: Build knowledge graph from notes (continuous builder)
- `neo4j-query`: Query the Neo4j graph (placeholder for future implementation)
- `neo4j-graph-builder-up/down/restart/logs`: Manage graph builder service
- `neo4j-setup`: Complete Neo4j setup (vector + graph seeding)

### Technical Improvements
- **Strict JSON Schema**: Implemented strict JSON schema validation for graph types using `WithJsonSchema` and `ConfigDict(extra='forbid')`
- **Deduplication**: Added post-processing to remove duplicate entities and relationships before storing in Neo4j
- **Error Handling**: Improved error handling for JSON parsing, Cypher query validation, and relationship type validation
- **Token Limits**: Increased `max_tokens` to 8000 for graph builder agent to handle large entity lists
- **Optional Prometheus**: Made Prometheus metrics optional for seeder/graph-builder containers

## Impact

- **Knowledge Graph**: Enables building a structured knowledge graph from unstructured NotePlan notes
- **Graph-Powered RAG**: Foundation for combining vector search with graph patterns for enhanced query responses
- **Entity Extraction**: Automated extraction of entities (people, projects, topics, dates, etc.) and relationships
- **Scalable Architecture**: Docker-based services with volume mounts enable rapid development iteration
- **Strict Schema Validation**: Ensures consistent, validated output from graph builder agent for reliable graph construction


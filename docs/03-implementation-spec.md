# Implementation Specification: Knowledge Agents Note Query System

## Executive Summary

This document provides a detailed technical specification for implementing the Knowledge Agents API service - an AI-powered system that answers questions about personal notes using semantic search and OpenAI agents. The system ingests NotePlan markdown files, creates embeddings, and provides intelligent answers based on note content.

## Architecture Overview

### System Architecture
- **Frontend**: FastAPI web framework providing REST API endpoints
- **Agent Layer**: OpenAI Agents framework for intelligent note query processing
- **Database Layer**: PostgreSQL with SQLAlchemy ORM for Plans/Buckets/Tasks
- **Vector Store**: Qdrant for semantic search across note embeddings
- **LLM Integration**: LiteLLM proxy connecting to LM Studio (local models)
- **Ingestion Layer**: Seeder service for parsing and seeding NotePlan files

### Component Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI API   │────│  Note Query     │────│   PostgreSQL    │
│   Endpoints     │    │  Agent          │    │   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Input/Output  │    │  Semantic       │    │   Qdrant        │
│   Guardrails    │    │  Search         │    │   Vector Store  │
│   (Validation)  │    │  (RAG)          │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Project Structure

### Directory Layout
```
knowledge-agents/
├── src/                          # Source code
│   ├── knowledge_agents/         # Main application
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI application
│   │   ├── database/             # Database layer
│   │   │   ├── models/           # SQLAlchemy models
│   │   │   │   ├── plan.py       # Plan model
│   │   │   │   ├── bucket.py     # Bucket model
│   │   │   │   └── task.py       # Task model
│   │   │   ├── queries/          # Database queries
│   │   │   │   ├── query_plans.py
│   │   │   │   ├── query_buckets.py
│   │   │   │   ├── query_tasks.py
│   │   │   │   └── query_vector_store.py
│   │   │   └── sessions.py       # Database sessions
│   │   ├── agents/               # OpenAI Agents
│   │   │   └── note_query_agent.py
│   │   ├── guardrails/           # Guardrail modules
│   │   │   ├── input/
│   │   │   │   └── note_query_guardrail.py
│   │   │   └── output/
│   │   │       └── judge_note_answer_guardrail.py
│   │   ├── services/             # Business logic
│   │   │   └── note_query_service.py
│   │   ├── routers/              # FastAPI routers
│   │   │   ├── base.py
│   │   │   └── note_query.py
│   │   ├── types/                # Type definitions
│   │   │   ├── note.py           # Note query types
│   │   │   ├── request.py
│   │   │   └── response.py
│   │   ├── utils/                # Utilities
│   │   │   └── vector_store_utils.py
│   │   └── config/               # Configuration
│   │       ├── api_config.py
│   │       └── secrets_config.py
│   └── notes/                    # NotePlan parsing package
│       ├── __init__.py
│       ├── parser.py             # Markdown parsing
│       ├── traversal.py          # File discovery
│       ├── filter.py             # File filtering
│       ├── generators.py         # Content generators
│       └── noteplan_structure.py # Structure documentation
├── scripts/                      # Utility scripts
│   ├── seed_database.py          # Database seeding
│   └── seed_vector_store.py      # Vector store seeding
├── tst/                          # Tests
│   ├── unit/
│   │   └── notes/
│   │       └── test_parser.py
│   ├── integration/
│   │   └── database/
│   │       ├── test_database_queries.py
│   │       └── test_vector_store.py
│   └── fixtures/
├── data/                         # Data files
│   └── 01-init-db.sql            # Database schema
├── config/                       # Configuration files
│   └── litellm_config.yaml       # LiteLLM proxy config
├── Dockerfile                    # Main Dockerfile
├── docker-compose.yml            # Docker Compose config
├── requirements.txt              # Dependencies
├── requirements-seeder.txt       # Seeder dependencies
└── Makefile                      # Build automation
```

## Core Components

### 1. Note Query Agent

**Purpose**: Answer questions about notes using semantic search and AI synthesis.

**Location**: `src/knowledge_agents/agents/note_query_agent.py`

**Flow**:
1. **Input Guardrail**: Validates query is a question about notes
2. **Semantic Search**: Finds relevant note files using Qdrant vector search
3. **Agent Processing**: Synthesizes answer from relevant notes using LLM
4. **Output Guardrail**: Validates answer quality

**Key Features**:
- Semantic search to find relevant notes
- AI-powered answer synthesis
- File citation tracking
- Guardrail validation

### 2. Database Models

**Plans** (`src/knowledge_agents/database/models/plan.py`):
- Daily plans (plan_type='daily') with plan_date
- Goal-focused plans (plan_type='goal') with goal_target_date
- One-to-many relationship with Buckets

**Buckets** (`src/knowledge_agents/database/models/bucket.py`):
- Represent markdown header sections
- Belong to a Plan
- One-to-many relationship with Tasks
- Ordered by order_index

**Tasks** (`src/knowledge_agents/database/models/task.py`):
- Represent markdown todos
- Can belong to a Bucket (or be at plan root)
- Recursive relationship (parent_task_id for subtasks)
- Support status, priority, due_date

### 3. NotePlan Parsing Package

**Location**: `src/notes/`

**Components**:
- **`parser.py`**: Parses markdown to extract structure (headers, todos)
- **`traversal.py`**: Discovers NotePlan files (daily plans, recent files)
- **`filter.py`**: Filters out system files (Caches, .DS_Store)
- **`generators.py`**: Generators for yielding processed content
- **`noteplan_structure.py`**: Documents NotePlan structure conventions

**Key Features**:
- Markdown to HTML conversion for robust parsing
- Header hierarchy tracking
- Todo extraction with completion status
- Section hierarchy preservation

### 4. Vector Store Integration

**Purpose**: Semantic search across note file content.

**Components**:
- **Qdrant Client**: Vector database for embeddings
- **Embedding Generation**: Uses LiteLLM proxy embedding model
- **File Metadata**: Stores file path, name, modification time, size

**Search Flow**:
1. User query → Generate query embedding
2. Vector search in Qdrant → Find top-N similar files
3. Return file metadata with similarity scores

### 5. Seeder Services

**Database Seeder** (`scripts/seed_database.py`):
- Parses daily plan files
- Creates Plan records
- Creates Bucket records from headers
- Creates Task records from todos
- Maintains hierarchy relationships

**Vector Store Seeder** (`scripts/seed_vector_store.py`):
- Discovers NotePlan files from last month
- Generates embeddings for file content
- Stores embeddings in Qdrant with file metadata

## Technology Stack

### Core Dependencies
- **FastAPI**: Web framework
- **OpenAI Agents**: Agent framework
- **SQLAlchemy**: ORM for PostgreSQL
- **Qdrant Client**: Vector database client
- **LiteLLM**: LLM proxy and routing
- **Pydantic**: Data validation

### LLM Configuration
- **LiteLLM Proxy**: Routes requests to LM Studio
- **Completion Model**: `lm_studio/qwen3-coder-30b`
- **Embedding Model**: `lm_studio/text-embedding-qwen3-embedding-8b`
- **Vector Size**: 4096 dimensions

## API Endpoints

### POST /api/v1/notes/query

Query your notes and get AI-powered answers.

**Request Body**:
```json
{
  "query": "What are my tasks for today?"
}
```

**Response**:
```json
{
  "request_id": "abc123",
  "answer": "Based on your notes, you have...",
  "reasoning": "Answer generated from relevant notes.",
  "relevant_files": [
    {
      "file_path": "2025-01-15.md",
      "file_name": "2025-01-15.md",
      "similarity_score": 0.92,
      "modified_at": "2025-01-15T08:00:00"
    }
  ],
  "original_query": "What are my tasks for today?",
  "query_answered": true,
  "guardrails_tripped": []
}
```

## Implementation Details

### Note Query Flow

1. **Input Validation**:
   - Guardrail checks if query is a valid question
   - Validates query length and format

2. **Semantic Search**:
   - Generate embedding for user query
   - Search Qdrant for top-N similar files
   - Return file metadata with scores

3. **Answer Generation**:
   - Agent receives query + relevant files
   - Synthesizes answer from note content
   - Provides reasoning for answer

4. **Output Validation**:
   - Guardrail checks answer quality
   - Validates answer completeness
   - Ensures answer is helpful

### Database Seeding Flow

1. **File Discovery**:
   - Traverse NotePlan directory
   - Find daily plan files (YYYY-MM-DD.md)
   - Filter out system files

2. **Markdown Parsing**:
   - Parse markdown to HTML
   - Extract headers as Buckets
   - Extract todos as Tasks
   - Track hierarchy relationships

3. **Database Population**:
   - Create Plan records
   - Create Bucket records with hierarchy
   - Create Task records linked to buckets
   - Handle recursive task relationships

4. **Vector Store Population**:
   - Generate embeddings for file content
   - Store embeddings with file metadata
   - Index for fast semantic search

## Testing Strategy

### Unit Tests
- Markdown parsing logic
- File filtering logic
- Database query methods
- Vector store utilities

### Integration Tests
- End-to-end note query flow
- Database seeding process
- Vector store seeding process
- Guardrail validation

### Test Data
- Mock NotePlan files
- Test database fixtures
- Test vector store collections

## Deployment

### Docker Compose Services
- **postgres**: PostgreSQL database
- **qdrant**: Qdrant vector store
- **llm-proxy**: LiteLLM proxy server
- **app**: FastAPI application
- **seeder**: Seeding service (runs on demand)

### Volume Mounts
- NotePlan directory → `/noteplan` in seeder container
- Database data → Persistent volume
- Vector store data → Persistent volume

### Environment Variables
- Database connection settings
- LiteLLM proxy configuration
- NotePlan directory path
- API keys (via Docker secrets)

## Future Enhancements

- **Multi-Plan Support**: Support goal-focused plans
- **Task Management**: API endpoints for task CRUD operations
- **Note Editing**: Update notes through API
- **Advanced Search**: Filter by date, plan type, task status
- **Conversation History**: Maintain context across queries
- **Note Templates**: Support for note templates
- **Export**: Export notes to various formats

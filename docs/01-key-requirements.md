# Key Requirements

## Core Functionality
- Create an API service that answers questions about personal notes
- Leverage semantic search to find relevant note files
- Use LLM to synthesize answers from note content
- API should accept natural language queries about notes
- API should return structured output with answers and relevant file citations
- Service must integrate with an LLM service (via LiteLLM proxy to LM Studio)

## Business Logic
- Parse NotePlan markdown files to extract structure (Plans, Buckets, Tasks)
- Support daily plans and goal-focused plans
- Track task hierarchy (tasks can have subtasks)
- Respect markdown header hierarchy when creating buckets
- Generate embeddings for semantic search across note files
- Filter out system files (Caches directories, .DS_Store)
- Provide answers based on actual note content only

## Technical Constraints
- Use Python
- Use FastAPI framework
- Use PostgreSQL for structured data
- Use Qdrant for vector embeddings
- Use LiteLLM proxy for LLM access
- Use LM Studio for local model execution
- Code quality weighted more than code style
- Must prioritize and estimate work effectively

## Data Model Requirements
- **Plans**: plan_id, title, description, plan_type (daily/goal), plan_date, goal_target_date
- **Buckets**: bucket_id, plan_id, name, description, order_index
- **Tasks**: task_id, bucket_id, parent_task_id (for subtasks), title, description, status, priority, order_index, due_date
- Support recursive task relationships (tasks can have subtasks)
- Support hierarchical bucket structure from markdown headers

## NotePlan Integration
- Parse NotePlan markdown files from local directory
- Extract daily plans (files matching YYYY-MM-DD.md pattern)
- Parse markdown headers as buckets
- Parse markdown todos as tasks
- Maintain header hierarchy (H1 → H2 → H3, etc.)
- Generate embeddings for semantic search
- Store file metadata (path, name, modification time, size)

## Deliverables
- API service that answers questions about notes
- Semantic search across note files
- Database schema for Plans/Buckets/Tasks
- NotePlan file parsing and ingestion
- Tests that prove the service meets requirements
- Documentation of architecture and setup
- Instructions for setting up environment

## Success Criteria
- API correctly answers questions based on note content
- Semantic search finds relevant notes
- Database properly stores Plans/Buckets/Tasks from NotePlan files
- Markdown parsing correctly extracts hierarchy
- Answers are accurate and cite relevant files
- Service performs well under expected load
- Code is clear and well-documented

## Ambiguous Requirements & Assumptions

### Assumptions Made
- NotePlan directory structure is accessible via Docker volume mount
- Markdown files use standard markdown syntax
- Daily plans follow YYYY-MM-DD.md naming convention
- Tasks are represented as markdown todos ([ ] or [x])
- Headers represent sections/buckets
- LiteLLM proxy provides OpenAI-compatible interface
- LM Studio is running locally and accessible
- Vector embeddings are sufficient for semantic search

### Clarifying Questions
- What level of accuracy is expected for note queries?
- Should the system support queries across all notes or filter by date?
- How should the system handle conflicting information across notes?
- What is the expected response time for queries?
- Should the system provide confidence scores for answers?
- How should the system handle queries about notes that don't exist?

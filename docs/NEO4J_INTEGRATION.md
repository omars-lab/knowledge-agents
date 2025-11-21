# Neo4j Integration for Knowledge Graph

This document describes the Neo4j integration for building and querying a knowledge graph from your NotePlan notes.

## Overview

The Neo4j integration provides three main components:

1. **Vector Store Seeding** - Loads note embeddings into Neo4j for semantic search
2. **Graph Building** - Extracts entities and relationships from notes to build a knowledge graph
3. **Graph Querying** - Queries the graph to answer questions about your notes

## Prerequisites

1. **Neo4j Desktop** - Install and run Neo4j Desktop locally
   - Default connection: `bolt://localhost:7687`
   - Default username: `neo4j`
   - Default password: Set during Neo4j Desktop setup

2. **Environment Variables** - Set these in your environment or `.env` file:
   ```bash
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password
   NEO4J_DATABASE=neo4j
   ```

## Scripts

### 1. Seed Neo4j Vector Store

Loads note embeddings into Neo4j for semantic search.

**Usage:**
```bash
# From project root
python scripts/seed_neo4j_vector_store.py
```

**What it does:**
- Reads NotePlan files from the last month
- Generates embeddings using LiteLLM proxy
- Stores embeddings in Neo4j with vector index
- Creates `Note` nodes with embeddings

**Docker:**
```bash
docker-compose run --rm seeder python /app/scripts/seed_neo4j_vector_store.py
```

### 2. Seed Neo4j Graph Database

Processes notes to extract entities and relationships, building a knowledge graph with proper schema.

**Usage:**
```bash
# From project root
python scripts/seed_graph_database.py
```

**What it does:**
- Sets up graph schema (indexes and constraints)
- Reads NotePlan files from the last month
- Uses graph builder agent to extract:
  - Entities (people, projects, topics, concepts, dates, locations)
  - Relationships between entities
  - Insights and facts
- Creates graph nodes and relationships in Neo4j
- Links notes to entities via `CONTAINS` relationships
- Sets up proper indexes for query performance

**Docker:**
```bash
docker-compose run --rm seeder python /app/scripts/seed_graph_database.py
```

**Makefile:**
```bash
make neo4j-seed-graph
```

### 3. Build Neo4j Graph (Continuous)

Continuously processes notes and updates the knowledge graph. This is a wrapper around the seeding logic for continuous operation.

**Usage:**
```bash
# From project root
python scripts/build_neo4j_graph.py
```

**What it does:**
- Reuses `seed_graph_database.py` logic
- Designed to run as a continuous service
- Processes new notes as they're added/updated

**Docker:**
```bash
docker-compose up neo4j-graph-builder
```

The graph builder service runs continuously and processes new notes as they're added.

### 4. Query Neo4j Graph

Queries the graph to answer questions about your notes.

**Usage:**
```bash
# Interactive mode
python scripts/query_neo4j_graph.py

# Single question
python scripts/query_neo4j_graph.py --question "What projects am I working on?"
```

**What it does:**
- Performs vector search to find relevant notes
- Uses graph patterns to find related entities
- Combines vector search and graph context
- Uses LLM to synthesize answers

**Example queries:**
- "What projects am I working on?"
- "Who did I mention in my notes this week?"
- "What are the main topics in my notes?"
- "What relationships exist between my projects?"

## Architecture

### Vector Search
- Uses LangChain's `Neo4jVector` for semantic search
- Embeds notes using LiteLLM proxy (local LLM)
- Stores embeddings in Neo4j with vector index
- Enables similarity search across notes

### Knowledge Graph
- Extracts structured information from notes
- Creates entity nodes (Person, Project, Topic, etc.)
- Creates relationships (RELATED_TO, WORKS_ON, MENTIONS, etc.)
- Links notes to entities via `CONTAINS` relationships

### Graph-Powered RAG
- Combines vector search with graph patterns
- Uses graph context to improve answer quality
- Leverages entity relationships for better understanding
- Provides more contextual and accurate answers

## Configuration

### Settings

Add to your `Settings` class or environment variables:

```python
# Neo4j Configuration
neo4j_uri: str = "bolt://localhost:7687"
neo4j_username: str = "neo4j"
neo4j_password: str = "password"
neo4j_database: str = "neo4j"
neo4j_vector_index_name: str = "note_embeddings"
```

### Docker Compose

The `neo4j-graph-builder` service is configured in `docker-compose.yml`:

```yaml
neo4j-graph-builder:
  environment:
    - NEO4J_URI=${NEO4J_URI:-bolt://host.docker.internal:7687}
    - NEO4J_USERNAME=${NEO4J_USERNAME:-neo4j}
    - NEO4J_PASSWORD=${NEO4J_PASSWORD:-password}
```

**Note:** For Docker, use `host.docker.internal:7687` to connect to Neo4j Desktop running on the host.

## Graph Schema

### Node Types

- **Note**: Represents a NotePlan file
  - Properties: `file_path` (unique), `file_name`, `modified_at`, `file_size`, `content`, `text`, `embedding`, `last_processed`
  - Constraints: `file_path` is unique
  - Indexes: `file_path`, `last_processed`
  
- **Entity**: Represents extracted entities
  - Properties: `name` (unique), `type` (Person|Project|Topic|Concept|Date|Location), additional properties
  - Constraints: `name` is unique
  - Indexes: `name`, `type`

### Relationship Types

- **CONTAINS**: Note → Entity (note contains entity)
- **RELATED_TO**: Entity → Entity (entities are related)
- **WORKS_ON**: Entity → Entity (person works on project)
- **MENTIONS**: Entity → Entity (entity mentions another)
- **REFERENCES**: Note → Relationship (note references relationship)

## Workflow

1. **Initial Setup:**
   ```bash
   # Start Neo4j Desktop
   # Ensure it's running on bolt://localhost:7687
   
   # Seed vector store
   make neo4j-seed-vector
   # or: python scripts/seed_neo4j_vector_store.py
   
   # Seed graph database (sets up schema and initial data)
   make neo4j-seed-graph
   # or: python scripts/seed_graph_database.py
   ```

2. **Ongoing Updates:**
   ```bash
   # Run graph builder service (processes new notes continuously)
   make neo4j-graph-builder-up
   # or: docker-compose up neo4j-graph-builder
   ```

3. **Querying:**
   ```bash
   # Interactive query mode
   make neo4j-query
   # or: python scripts/query_neo4j_graph.py
   
   # Single question
   make neo4j-query QUERY="What projects am I working on?"
   ```

## Differences from Qdrant

| Feature | Qdrant | Neo4j |
|---------|--------|-------|
| Vector Search | ✅ | ✅ |
| Knowledge Graph | ❌ | ✅ |
| Entity Extraction | ❌ | ✅ |
| Relationship Mapping | ❌ | ✅ |
| Graph-Powered RAG | ❌ | ✅ |

Neo4j provides both vector search and knowledge graph capabilities, enabling more sophisticated querying and understanding of your notes.

## Troubleshooting

### Connection Issues

If you can't connect to Neo4j Desktop from Docker:

1. Ensure Neo4j Desktop is running
2. Check the connection URI (should be `bolt://localhost:7687` for local, `bolt://host.docker.internal:7687` for Docker)
3. Verify username and password
4. Check Neo4j Desktop firewall settings

### Vector Index Issues

If vector index creation fails:

1. Ensure you're using Neo4j 5.x or later (vector indexes require Neo4j 5+)
2. LangChain's `Neo4jVector.from_texts()` will create the index automatically
3. You can also create the index manually in Neo4j Browser

### Graph Building Issues

If graph building fails:

1. Check LLM proxy is running and accessible
2. Verify NotePlan directory is mounted correctly
3. Check logs for specific errors
4. Ensure Neo4j has enough memory allocated

## Future Enhancements

- [ ] Graph visualization in Neo4j Browser
- [ ] Automatic graph updates on note changes
- [ ] Graph-based recommendations
- [ ] Temporal graph analysis (track changes over time)
- [ ] Graph ML for entity classification and relationship prediction


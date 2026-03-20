"""
Utility functions for Neo4j graph operations.

This module provides reusable functions for:
- Setting up graph schema (indexes and constraints)
- Creating graph nodes and relationships from agent output
- Extracting data from note files
- Reading NotePlan files with metadata
- Storing notes with embeddings in Neo4j
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, List, Dict, Tuple

from neo4j import GraphDatabase

if TYPE_CHECKING:
    from ..dependencies import Dependencies
    from ..types.graph import GraphBuilderAgentOutput

logger = logging.getLogger(__name__)


def setup_graph_schema(driver: GraphDatabase.driver, database: str = "neo4j") -> None:
    """
    Set up Neo4j graph schema: indexes and constraints.
    
    Creates the necessary database constraints and indexes for efficient graph operations.
    This should be called once before loading data into Neo4j.
    
    **Constraints Created:**
    - `note_file_path`: Ensures Note nodes have unique file_path values
    - `entity_name`: Ensures Entity nodes have unique name values
    
    **Indexes Created:**
    - `note_file_path_idx`: Index on Note.file_path for fast lookups
    - `entity_name_idx`: Index on Entity.name for fast lookups
    - `entity_type_idx`: Index on Entity.type for filtering by type
    - `note_last_processed_idx`: Index on Note.last_processed for tracking updates
    
    **Usage:**
    ```python
    from neo4j import GraphDatabase
    from knowledge_agents.utils.graph_utils import setup_graph_schema
    
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
    setup_graph_schema(driver, database="knowledge")
    ```
    
    **Note:** This function is idempotent - it can be called multiple times safely.
    Constraints and indexes are created with `IF NOT EXISTS`, so existing ones won't cause errors.
    
    Args:
        driver: Neo4j driver instance (from `neo4j.GraphDatabase.driver()`)
        database: Neo4j database name (default: "neo4j")
        
    Raises:
        Exception: If Neo4j connection fails or database operations fail
        
    Example:
        ```python
        # In a notebook or script
        from knowledge_agents.clients.neo4j_client import Neo4jClientManager
        from knowledge_agents.utils.graph_utils import setup_graph_schema
        
        neo4j_manager = Neo4jClientManager(settings=settings)
        driver = neo4j_manager.get_driver()
        setup_graph_schema(driver, settings.neo4j_database)
        ```
    """
    logger.info("Setting up Neo4j graph schema (indexes and constraints)...")
    
    with driver.session(database=database) as session:
        # Create constraints for uniqueness
        constraints = [
            # Note nodes should have unique file_path
            "CREATE CONSTRAINT note_file_path IF NOT EXISTS FOR (n:Note) REQUIRE n.file_path IS UNIQUE",
            # Entity nodes should have unique name
            "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
        ]
        
        for constraint in constraints:
            try:
                session.run(constraint)
                logger.debug(f"Created constraint: {constraint.split()[2]}")
            except Exception as e:
                # Constraint might already exist
                logger.debug(f"Constraint may already exist: {e}")
        
        # Create indexes for better query performance
        indexes = [
            # Index on Note file_path (already unique via constraint, but explicit index helps)
            "CREATE INDEX note_file_path_idx IF NOT EXISTS FOR (n:Note) ON (n.file_path)",
            # Index on Entity name (already unique via constraint, but explicit index helps)
            "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            # Index on Entity type for filtering
            "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type)",
            # Index on Note last_processed for tracking updates
            "CREATE INDEX note_last_processed_idx IF NOT EXISTS FOR (n:Note) ON (n.last_processed)",
        ]
        
        for index in indexes:
            try:
                session.run(index)
                logger.debug(f"Created index: {index.split()[2]}")
            except Exception as e:
                # Index might already exist
                logger.debug(f"Index may already exist: {e}")
        
        logger.info("✅ Graph schema setup completed")


def create_graph_nodes_and_relationships(
    driver: GraphDatabase.driver,
    file_path: str,
    agent_output: "GraphBuilderAgentOutput",
    database: str = "neo4j",
) -> tuple[int, int]:
    """
    Create nodes and relationships in Neo4j from agent output.
    
    Processes the output from `run_graph_builder_agent()` and creates the corresponding
    graph structure in Neo4j:
    
    1. Creates or updates a Note node for the file
    2. Creates Entity nodes for each extracted entity (MERGE to avoid duplicates)
    3. Creates CONTAINS relationships between Note and Entity nodes
    4. Creates relationships between Entity nodes based on extracted relationships
    
    **Graph Structure Created:**
    ```
    (Note {file_path: "path/to/file.md"})
        -[:CONTAINS]-> (Entity {name: "Entity1", type: "Person"})
        -[:CONTAINS]-> (Entity {name: "Entity2", type: "Project"})
    
    (Entity {name: "Entity1"})
        -[:WORKS_ON]-> (Entity {name: "Entity2"})
    ```
    
    **Usage:**
    ```python
    from knowledge_agents.utils.graph_utils import create_graph_nodes_and_relationships
    from knowledge_agents.agents.graph_builder_agent import run_graph_builder_agent
    
    # Extract entities/relationships from a note
    agent_output = await run_graph_builder_agent(
        note_content="John works on the AI project...",
        file_path="notes/project.md",
        dependencies=dependencies
    )
    
    # Store in Neo4j
    entities_count, rels_count = create_graph_nodes_and_relationships(
        driver=driver,
        file_path="notes/project.md",
        agent_output=agent_output,
        database="knowledge"
    )
    print(f"Created {entities_count} entities and {rels_count} relationships")
    ```
    
    **Input Example:**
    ```python
    agent_output = GraphBuilderAgentOutput(
        entities=[
            Entity(name="John", type="Person", properties={}),
            Entity(name="AI project", type="Project", properties={})
        ],
        relationships=[
            Relationship(
                from_entity="John",
                to_entity="AI project",
                type="WORKS_ON",
                properties={}
            )
        ],
        insights=["John is working on the AI project"]
    )
    
    entities, relationships = create_graph_nodes_and_relationships(
        driver, "notes/project.md", agent_output, "knowledge"
    )
    # Returns: (2, 1) - 2 entities created, 1 relationship created
    ```
    
    **Notes:**
    - Entity nodes are merged by name (same name = same node, even if type differs)
    - Relationship types are validated against allowed types (invalid types default to RELATED_TO)
    - Empty entity names or relationships are skipped
    - The Note node's `last_processed` timestamp is updated to current time
    
    Args:
        driver: Neo4j driver instance (from `neo4j.GraphDatabase.driver()`)
        file_path: Relative path to the note file (e.g., "2025-01-15.md" or "notes/project.md").
                  This is stored as the Note node's `file_path` property.
        agent_output: GraphBuilderAgentOutput containing:
            - `entities`: List of Entity objects with name, type, and properties
            - `relationships`: List of Relationship objects with from_entity, to_entity, type, and properties
            - `insights`: List of insight strings (not stored in graph, but included in output)
        database: Neo4j database name (default: "neo4j")
        
    Returns:
        Tuple[int, int]: Number of entities processed and relationships created.
        Note: The count includes both newly created and existing (matched) entities/relationships.
        
    Raises:
        Exception: If Neo4j operations fail (connection issues, query errors, etc.)
        
    Example:
        ```python
        # In a notebook processing multiple files
        extracted_data = [
            ("2025-01-15.md", agent_output_1),
            ("notes/project.md", agent_output_2),
        ]
        
        total_entities = 0
        total_relationships = 0
        for file_path, output in extracted_data:
            entities, rels = create_graph_nodes_and_relationships(
                driver, file_path, output, settings.neo4j_database
            )
            total_entities += entities
            total_relationships += rels
        
        print(f"Total: {total_entities} entities, {total_relationships} relationships")
        ```
    """
    entities_created = 0
    relationships_created = 0
    
    with driver.session(database=database) as session:
        # Create Note node first
        session.run(
            """
            MERGE (n:Note {file_path: $file_path})
            SET n.last_processed = datetime()
            """,
            file_path=file_path,
        )
        
        # Create entity nodes
        for entity in agent_output.entities:
            entity_name = entity.name
            entity_type = entity.type
            properties = entity.properties or {}
            
            if not entity_name:
                continue
            
            # Create entity node (use Entity as base label, add type as property)
            # This avoids creating too many node types
            result = session.run(
                """
                MERGE (e:Entity {name: $name})
                ON CREATE SET e.type = $entity_type, e += $properties
                ON MATCH SET e.type = $entity_type, e += $properties
                WITH e
                MATCH (n:Note {file_path: $file_path})
                MERGE (n)-[:CONTAINS]->(e)
                RETURN e
                """,
                name=entity_name,
                entity_type=entity_type,
                properties=properties,
                file_path=file_path,
            )
            
            # Check if entity was created (ON CREATE) or matched (ON MATCH)
            record = result.single()
            if record:
                entities_created += 1
        
        # Create relationships between entities
        for rel in agent_output.relationships:
            from_entity = rel.from_entity
            to_entity = rel.to_entity
            rel_type = rel.type
            properties = rel.properties or {}
            
            if not from_entity or not to_entity:
                continue
            
            # Use parameterized relationship type (safer, but requires dynamic query construction)
            # For now, validate relationship type to prevent injection
            valid_rel_types = [
                "RELATED_TO", "WORKS_ON", "MENTIONS", "REFERENCES",
                "OCCURS_AT", "BELONGS_TO", "PART_OF", "CONTAINS"
            ]
            if rel_type not in valid_rel_types:
                logger.warning(f"Invalid relationship type: {rel_type}, using RELATED_TO")
                rel_type = "RELATED_TO"
            
            result = session.run(
                f"""
                MATCH (from:Entity {{name: $from_name}})
                MATCH (to:Entity {{name: $to_name}})
                MERGE (from)-[r:{rel_type}]->(to)
                ON CREATE SET r += $properties
                ON MATCH SET r += $properties
                RETURN r
                """,
                from_name=from_entity,
                to_name=to_entity,
                properties=properties,
            )
            
            record = result.single()
            if record:
                relationships_created += 1
    
    return entities_created, relationships_created


async def extract_from_note_file(
    file_path: Path,
    relative_path: str,
    dependencies: "Dependencies",
) -> tuple[str, "GraphBuilderAgentOutput" | None]:
    """
    Extract entities and relationships from a note file using the graph builder agent.
    
    Reads a NotePlan file and uses the LLM-powered graph builder agent to extract
    structured information (entities, relationships, insights) from the note content.
    
    **Process:**
    1. Reads the note file content using `read_noteplan_file()`
    2. Calls `run_graph_builder_agent()` to extract structured data
    3. Returns the extracted data or None if extraction fails
    
    **Usage:**
    ```python
    import asyncio
    from pathlib import Path
    from knowledge_agents.utils.graph_utils import extract_from_note_file
    from knowledge_agents.dependencies import Dependencies
    
    dependencies = Dependencies(settings=settings)
    file_path = Path("/noteplan/2025-01-15.md")
    relative_path = "2025-01-15.md"
    
    # Extract (async function)
    path, output = await extract_from_note_file(file_path, relative_path, dependencies)
    
    # Or in a sync context (e.g., Jupyter notebook with nest_asyncio):
    path, output = asyncio.run(extract_from_note_file(file_path, relative_path, dependencies))
    
    if output:
        print(f"Extracted {len(output.entities)} entities")
        print(f"Extracted {len(output.relationships)} relationships")
    else:
        print("Extraction failed")
    ```
    
    **Input Example:**
    ```python
    file_path = Path("/Users/.../NotePlan3/2025-01-15.md")
    relative_path = "2025-01-15.md"  # Relative from NotePlan root
    dependencies = Dependencies(settings=settings)  # Contains LLM client, settings, etc.
    
    path, output = await extract_from_note_file(file_path, relative_path, dependencies)
    ```
    
    **Output Example:**
    ```python
    # Success case:
    (
        "2025-01-15.md",
        GraphBuilderAgentOutput(
            entities=[
                Entity(name="John", type="Person", properties={}),
                Entity(name="AI project", type="Project", properties={})
            ],
            relationships=[
                Relationship(
                    from_entity="John",
                    to_entity="AI project",
                    type="WORKS_ON",
                    properties={}
                )
            ],
            insights=["John is working on the AI project"]
        )
    )
    
    # Failure case:
    ("2025-01-15.md", None)
    ```
    
    **Notes:**
    - This function is async and must be called with `await` or `asyncio.run()`
    - In Jupyter notebooks, use `nest_asyncio` to allow `asyncio.run()` calls
    - The `relative_path` is used as the `file_path` parameter when calling the agent
    - Errors are logged but not raised - the function returns None on failure
    
    Args:
        file_path: Full absolute path to the note file (e.g., 
                  `Path("/Users/.../NotePlan3/2025-01-15.md")`)
        relative_path: Relative path from NotePlan directory root (e.g., "2025-01-15.md").
                      This is used as the file identifier in the graph and agent output.
        dependencies: Dependencies container containing:
            - `settings`: Application settings (API keys, model config, etc.)
            - LLM client for running the graph builder agent
            
    Returns:
        Tuple[str, GraphBuilderAgentOutput | None]:
            - First element: The `relative_path` (same as input)
            - Second element: GraphBuilderAgentOutput with extracted data, or None if extraction failed
            
    Raises:
        Exception: Only if file reading fails (agent errors are caught and logged)
        
    Example:
        ```python
        # Processing multiple files in a loop
        files = [
            (Path("/noteplan/file1.md"), "file1.md"),
            (Path("/noteplan/file2.md"), "file2.md"),
        ]
        
        extracted_data = []
        for file_path, relative_path in files:
            path, output = await extract_from_note_file(
                file_path, relative_path, dependencies
            )
            if output:
                extracted_data.append((path, output))
                print(f"✅ {path}: {len(output.entities)} entities")
            else:
                print(f"❌ {path}: Extraction failed")
        ```
    """
    from ..notes.parser import read_noteplan_file
    from ..agents.graph_builder_agent import run_graph_builder_agent
    
    try:
        content = read_noteplan_file(file_path)
        agent_output = await run_graph_builder_agent(
            note_content=content,
            file_path=relative_path,
            dependencies=dependencies,
        )
        return relative_path, agent_output
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return relative_path, None


def read_noteplan_files_with_metadata(
    files: List[Tuple[Path, any]],
    noteplan_dir: Path,
    include_file_path_in_content: bool = False,
    skip_database_files: bool = True,
) -> Tuple[List[str], List[Dict[str, any]]]:
    """
    Read NotePlan files and build content and metadata lists for embedding.
    
    Processes a list of (file_path, mod_time) tuples, reads each file,
    and returns parallel lists of file contents and metadata dictionaries.
    
    **Process:**
    1. Iterates through files
    2. Filters out files that should be skipped (using `should_skip_file()`)
    3. Optionally filters out database files (.db, .sqlite, etc.)
    4. Reads file content using `read_noteplan_file()`
    5. Builds metadata dictionary with file_path, file_name, modified_at, file_size
    6. Optionally prepends file path to content for better context
    
    **Usage:**
    ```python
    from pathlib import Path
    from ..notes.traversal import get_files_from_last_month
    from knowledge_agents.utils.graph_utils import read_noteplan_files_with_metadata
    
    NOTEPLAN_DIR = Path("/noteplan")
    files = get_files_from_last_month(NOTEPLAN_DIR)
    
    # Read files with metadata
    file_contents, file_metadata = read_noteplan_files_with_metadata(
        files=files,
        noteplan_dir=NOTEPLAN_DIR,
        include_file_path_in_content=True,  # Prepend "File: {path}\n\n{content}"
        skip_database_files=True,
    )
    
    # Now generate embeddings
    embeddings = generate_embeddings(texts=file_contents, dependencies=dependencies)
    ```
    
    **Args:**
        files: List of (file_path: Path, mod_time) tuples from `get_files_from_last_month()`
        noteplan_dir: Base directory for NotePlan files (used for relative paths)
        include_file_path_in_content: If True, prepends "File: {relative_path}\n\n" to content
        skip_database_files: If True, skips .db, .sqlite, .sqlite3, .db-shm, .db-wal files
        
    **Returns:**
        Tuple of (file_contents: List[str], file_metadata: List[Dict[str, any]])
        - file_contents: List of file content strings (ready for embedding)
        - file_metadata: List of metadata dicts with keys: file_path, file_name, modified_at, file_size
        
    **Example:**
        ```python
        files = [(Path("/noteplan/2025-01-15.md"), datetime(...)), ...]
        contents, metadata = read_noteplan_files_with_metadata(files, Path("/noteplan"))
        
        # contents[0] = "# My Note\n\nContent here..."
        # metadata[0] = {
        #     "file_path": "2025-01-15.md",
        #     "file_name": "2025-01-15.md",
        #     "modified_at": "2025-01-15T10:30:00",
        #     "file_size": 1234
        # }
        ```
        
    **Note:** Files that fail to read are skipped (logged as errors but don't stop processing).
    """
    from ..notes.parser import read_noteplan_file
    from ..notes.filter import should_skip_file
    
    file_contents = []
    file_metadata = []
    
    for file_path, mod_time in files:
        # Skip filtered files
        if should_skip_file(file_path):
            logger.debug(f"Skipping filtered file: {file_path}")
            continue
        
        # Skip database files if requested
        if skip_database_files and file_path.suffix.lower() in {
            ".db", ".sqlite", ".sqlite3", ".db-shm", ".db-wal"
        }:
            logger.debug(f"Skipping database file: {file_path}")
            continue
        
        try:
            content = read_noteplan_file(file_path)
            relative_path = str(file_path.relative_to(noteplan_dir))
            
            # Optionally prepend file path to content
            if include_file_path_in_content:
                text_representation = f"File: {relative_path}\n\n{content}"
            else:
                text_representation = content
            
            file_contents.append(text_representation)
            file_metadata.append({
                "file_path": relative_path,
                "file_name": file_path.name,
                "modified_at": mod_time.isoformat(),
                "file_size": len(content),
            })
            logger.debug(f"Read file: {file_path.name} ({len(content)} chars)")
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            continue
    
    return file_contents, file_metadata


def store_notes_with_embeddings(
    driver: GraphDatabase.driver,
    embeddings: List[List[float]],
    file_metadata: List[Dict[str, any]],
    file_contents: List[str],
    database: str = "neo4j",
    progress_interval: int = 10,
) -> int:
    """
    Store notes with embeddings in Neo4j vector store.
    
    Creates or updates Note nodes with embeddings, metadata, and content.
    This function is used for populating the Neo4j vector store for semantic search.
    
    **Process:**
    1. Iterates through embeddings, metadata, and contents in parallel
    2. Uses MERGE to create or update Note nodes by file_path
    3. Sets properties: file_name, modified_at, file_size, content, text, embedding
    4. Logs progress at specified intervals
    
    **Usage:**
    ```python
    from neo4j import GraphDatabase
    from knowledge_agents.utils.graph_utils import store_notes_with_embeddings
    
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
    
    # After generating embeddings
    embeddings = generate_embeddings(texts=file_contents, dependencies=dependencies)
    
    # Store in Neo4j
    notes_stored = store_notes_with_embeddings(
        driver=driver,
        embeddings=embeddings,
        file_metadata=file_metadata,
        file_contents=file_contents,
        database="knowledge",
        progress_interval=10,  # Log every 10 notes
    )
    
    print(f"Stored {notes_stored} notes")
    ```
    
    **Args:**
        driver: Neo4j driver instance (from `neo4j.GraphDatabase.driver()`)
        embeddings: List of embedding vectors (each is a list of floats)
        file_metadata: List of metadata dicts (must match embeddings order)
        file_contents: List of file content strings (must match embeddings order)
        database: Neo4j database name (default: "neo4j")
        progress_interval: Log progress every N notes (default: 10, set to 0 to disable)
        
    **Returns:**
        Number of notes stored (equal to len(embeddings) if all succeed)
        
    **Example:**
        ```python
        # After reading files and generating embeddings
        notes_stored = store_notes_with_embeddings(
            driver=driver,
            embeddings=embeddings,
            file_metadata=[
                {"file_path": "2025-01-15.md", "file_name": "2025-01-15.md", ...},
                ...
            ],
            file_contents=["# Note 1\n\n...", "# Note 2\n\n...", ...],
            database="knowledge",
        )
        ```
        
    **Note:** 
    - All three lists (embeddings, file_metadata, file_contents) must have the same length
    - Uses MERGE so existing notes are updated, new ones are created
    - The `text` property is set to content for LangChain compatibility
    """
    with driver.session(database=database) as session:
        for idx, (embedding, metadata, content) in enumerate(
            zip(embeddings, file_metadata, file_contents)
        ):
            # Create or update Note node with embedding
            session.run(
                """
                MERGE (n:Note {file_path: $file_path})
                SET n.file_name = $file_name,
                    n.modified_at = $modified_at,
                    n.file_size = $file_size,
                    n.content = $content,
                    n.text = $text,
                    n.embedding = $embedding
                """,
                file_path=metadata["file_path"],
                file_name=metadata["file_name"],
                modified_at=metadata["modified_at"],
                file_size=metadata["file_size"],
                content=content,
                text=content,  # For LangChain compatibility
                embedding=embedding,
            )
            
            if progress_interval > 0 and (idx + 1) % progress_interval == 0:
                logger.info(f"Processed {idx + 1}/{len(embeddings)} notes...")
    
    return len(embeddings)


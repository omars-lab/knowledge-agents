#!/usr/bin/env python3
"""
Seed Neo4j Graph Database with Entities and Relationships from NotePlan Files

PURPOSE: Populate Neo4j graph database with entities, relationships, and insights extracted from NotePlan files
SCOPE: Read NotePlan files, extract entities/relationships using LLM agents, create graph structure with proper indexes

This script:
- Iterates through NotePlan files in /noteplan directory
- Uses graph builder agent to extract entities and relationships
- Creates Note, Entity nodes and relationships in Neo4j
- Sets up proper indexes and constraints
- Links notes to entities via CONTAINS relationships
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from knowledge_agents.config.api_config import Settings
from knowledge_agents.config.logging_config import setup_logging
from knowledge_agents.dependencies import Dependencies
from knowledge_agents.clients.neo4j_client import Neo4jClientManager
from knowledge_agents.agents.graph_builder_agent import run_graph_builder_agent
from notes.filter import should_skip_file
from notes.parser import read_noteplan_file
from notes.traversal import get_files_from_last_month

# Neo4j imports
from neo4j import GraphDatabase

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# NotePlan directory path
NOTEPLAN_DIR = Path("/noteplan")


def setup_graph_schema(driver: GraphDatabase.driver, database: str = "neo4j") -> None:
    """
    Set up Neo4j graph schema: indexes and constraints.
    
    Args:
        driver: Neo4j driver
        database: Neo4j database name
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
    agent_output,  # GraphBuilderAgentOutput
    database: str = "neo4j",
) -> tuple[int, int]:
    """
    Create nodes and relationships in Neo4j from agent output.
    
    Args:
        driver: Neo4j driver
        file_path: Path to the note file
        agent_output: GraphBuilderAgentOutput with extracted entities and relationships
        database: Neo4j database name
        
    Returns:
        Tuple of (entities_created, relationships_created)
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


async def process_note_file(
    file_path: Path,
    dependencies: Dependencies,
    driver: GraphDatabase.driver,
) -> tuple[int, int]:
    """
    Process a single note file and update the graph.
    
    Args:
        file_path: Path to note file
        dependencies: Dependencies container
        driver: Neo4j driver
        
    Returns:
        Tuple of (entities_created, relationships_created)
    """
    try:
        content = read_noteplan_file(file_path)
        relative_path = str(file_path.relative_to(NOTEPLAN_DIR))
        
        logger.info(f"Processing note: {relative_path}")
        
        # Extract entities and relationships using graph builder agent
        agent_output = await run_graph_builder_agent(
            note_content=content,
            file_path=relative_path,
            dependencies=dependencies,
        )
        
        # Deduplicate entities (same name and type)
        seen_entities = {}
        deduplicated_entities = []
        for entity in agent_output.entities:
            key = (entity.name, entity.type)
            if key not in seen_entities:
                seen_entities[key] = entity
                deduplicated_entities.append(entity)
        agent_output.entities = deduplicated_entities
        
        # Deduplicate relationships (same from, to, and type)
        seen_relationships = {}
        deduplicated_relationships = []
        for rel in agent_output.relationships:
            key = (rel.from_entity, rel.to_entity, rel.type)
            if key not in seen_relationships:
                seen_relationships[key] = rel
                deduplicated_relationships.append(rel)
        agent_output.relationships = deduplicated_relationships
        
        # Create graph nodes and relationships
        entities_created, relationships_created = create_graph_nodes_and_relationships(
            driver=driver,
            file_path=relative_path,
            agent_output=agent_output,
            database=dependencies.settings.neo4j_database,
        )
        
        logger.info(
            f"✅ Processed {relative_path}: "
            f"{entities_created} entities, "
            f"{relationships_created} relationships, "
            f"{len(agent_output.insights)} insights"
        )
        
        return entities_created, relationships_created
        
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
        return 0, 0


async def seed_graph_database_from_noteplan() -> None:
    """Main function to seed the graph database from NotePlan files."""
    logger.info("Starting Neo4j graph database seeding process from NotePlan files")

    try:
        # Initialize Settings and Dependencies
        settings = Settings()
        dependencies = Dependencies(settings=settings)

        # Get Neo4j driver
        neo4j_manager = Neo4jClientManager(settings=settings)
        driver = neo4j_manager.get_driver()

        # Set up graph schema (indexes and constraints)
        setup_graph_schema(driver, database=settings.neo4j_database)

        # Get files from last month
        files = get_files_from_last_month(NOTEPLAN_DIR)

        if not files:
            logger.warning(
                "No NotePlan files found from the last month. Nothing to seed."
            )
            return

        logger.info(f"Found {len(files)} files to process")

        # Process files concurrently (with limit to avoid overwhelming the LLM)
        semaphore = asyncio.Semaphore(3)  # Process 3 files at a time
        total_entities = 0
        total_relationships = 0

        async def process_with_semaphore(file_path, mod_time):
            nonlocal total_entities, total_relationships
            async with semaphore:
                entities, relationships = await process_note_file(
                    file_path, dependencies, driver
                )
                total_entities += entities
                total_relationships += relationships

        tasks = [
            process_with_semaphore(file_path, mod_time)
            for file_path, mod_time in files
            if not should_skip_file(file_path)
        ]

        await asyncio.gather(*tasks)

        # Verify graph
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(
                """
                MATCH (n)
                RETURN labels(n)[0] as label, COUNT(n) as count
                ORDER BY count DESC
                """
            )
            logger.info("Graph statistics:")
            for record in result:
                logger.info(f"  {record['label']}: {record['count']} nodes")
            
            # Count relationships
            rel_result = session.run(
                """
                MATCH ()-[r]->()
                RETURN type(r) as rel_type, COUNT(r) as count
                ORDER BY count DESC
                """
            )
            logger.info("Relationship statistics:")
            for record in rel_result:
                logger.info(f"  {record['rel_type']}: {record['count']} relationships")

        logger.info(
            f"✅ Successfully seeded graph database: "
            f"{total_entities} entities, {total_relationships} relationships created"
        )

    except Exception as e:
        logger.error(f"❌ Error seeding graph database: {e}", exc_info=True)
        raise
    finally:
        if 'driver' in locals():
            driver.close()


def main():
    """Entry point for the script."""
    try:
        asyncio.run(seed_graph_database_from_noteplan())
        logger.info("Graph database seeding completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()


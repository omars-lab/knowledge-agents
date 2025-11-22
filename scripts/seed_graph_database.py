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
from knowledge_agents.utils.graph_utils import (
    setup_graph_schema,
    create_graph_nodes_and_relationships,
    extract_from_note_file,
)
from notes.filter import should_skip_file
from notes.traversal import get_files_from_last_month

# Neo4j imports
from neo4j import GraphDatabase

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# NotePlan directory path
NOTEPLAN_DIR = Path("/noteplan")


# Functions setup_graph_schema and create_graph_nodes_and_relationships
# are now imported from knowledge_agents.utils.graph_utils


async def process_note_file(
    file_path: Path,
    dependencies: Dependencies,
    driver: GraphDatabase.driver,
) -> tuple[int, int]:
    """
    Process a single note file and update the graph.
    
    Uses `extract_from_note_file()` from graph_utils to extract data,
    then stores it in Neo4j using `create_graph_nodes_and_relationships()`.
    
    Args:
        file_path: Path to note file
        dependencies: Dependencies container
        driver: Neo4j driver
        
    Returns:
        Tuple of (entities_created, relationships_created)
    """
    try:
        relative_path = str(file_path.relative_to(NOTEPLAN_DIR))
        logger.info(f"Processing note: {relative_path}")
        
        # Extract entities and relationships using utility function
        path, agent_output = await extract_from_note_file(
            file_path=file_path,
            relative_path=relative_path,
            dependencies=dependencies,
        )
        
        if agent_output is None:
            logger.warning(f"Failed to extract data from {relative_path}")
            return 0, 0
        
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
        
        # Create graph nodes and relationships using utility function
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


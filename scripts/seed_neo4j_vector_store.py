#!/usr/bin/env python3
"""
Seed Neo4j Vector Store with NotePlan File Embeddings

PURPOSE: Populate Neo4j vector database with embeddings of NotePlan files
SCOPE: Read NotePlan files from /noteplan, filter by date, generate embeddings, store in Neo4j

This script:
- Iterates through files in /noteplan directory
- Filters files from the last month
- Generates embeddings using LiteLLM proxy
- Stores embeddings in Neo4j vector database for semantic search
"""

import logging
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from knowledge_agents.config.api_config import Settings
from knowledge_agents.config.logging_config import setup_logging
from knowledge_agents.dependencies import Dependencies
from knowledge_agents.utils.graph_utils import (
    read_noteplan_files_with_metadata,
    store_notes_with_embeddings,
)
from knowledge_agents.utils.vector_store_utils import generate_embeddings
from knowledge_agents.notes.traversal import get_files_from_last_month

# Neo4j imports
from neo4j import GraphDatabase

# Configure logging using centralized config
setup_logging()
logger = logging.getLogger(__name__)

# NotePlan directory path in container
NOTEPLAN_DIR = Path("/noteplan")


def seed_neo4j_vector_store_from_noteplan() -> None:
    """Main function to seed the Neo4j vector store from NotePlan files."""
    logger.info("Starting Neo4j vector store seeding process from NotePlan files")

    try:
        # Initialize Settings and Dependencies (explicit dependency injection)
        settings = Settings()
        dependencies = Dependencies(settings=settings)

        # Get files from last month
        files = get_files_from_last_month(NOTEPLAN_DIR)

        if not files:
            logger.warning(
                "No NotePlan files found from the last month. Nothing to seed."
            )
            return

        # Get Neo4j driver
        from knowledge_agents.clients.neo4j_client import Neo4jClientManager
        
        neo4j_manager = Neo4jClientManager(settings=settings)
        driver = neo4j_manager.get_driver()

        # Get embedding size from settings
        embedding_size = settings.get_embedding_size(
            settings.litellm_proxy_embedding_model
        )

        # Ensure vector index exists
        neo4j_manager.ensure_vector_index(vector_size=embedding_size)

        # Read file contents using utility function
        file_contents, file_metadata = read_noteplan_files_with_metadata(
            files=files,
            noteplan_dir=NOTEPLAN_DIR,
            include_file_path_in_content=True,  # Prepend "File: {path}\n\n{content}"
            skip_database_files=True,
        )

        if not file_contents:
            logger.warning("No file contents to embed. Exiting.")
            return

        logger.info(f"Generating embeddings for {len(file_contents)} files...")

        # Generate embeddings using dependencies (same as Qdrant script)
        try:
            embeddings = generate_embeddings(
                texts=file_contents,
                dependencies=dependencies,
                batch_size=10,  # Process in batches (same as Qdrant script)
                embedding_model=settings.litellm_proxy_embedding_model,
            )
            logger.info(f"Generated {len(embeddings)} embeddings")
        except Exception as e:
            import traceback
            logger.error(f"Error generating embeddings: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            raise

        # Store in Neo4j using utility function
        logger.info(f"Storing {len(embeddings)} notes in Neo4j...")
        notes_stored = store_notes_with_embeddings(
            driver=driver,
            embeddings=embeddings,
            file_metadata=file_metadata,
            file_contents=file_contents,
            database=settings.neo4j_database,
            progress_interval=10,
        )
        logger.info(f"Stored {notes_stored} notes with embeddings")

        # Verify insertion
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run("MATCH (n:Note) RETURN COUNT(n) as count")
            count = result.single()["count"]
            logger.info(
                f"✅ Successfully seeded Neo4j vector store: {count} notes in database"
            )

    except Exception as e:
        logger.error(f"❌ Error seeding Neo4j vector store: {e}")
        raise
    finally:
        if 'driver' in locals():
            driver.close()


def main():
    """Entry point for the script."""
    try:
        seed_neo4j_vector_store_from_noteplan()
        logger.info("Neo4j vector store seeding completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Seed Qdrant Vector Store with NotePlan File Embeddings

PURPOSE: Populate Qdrant vector database with embeddings of NotePlan files
SCOPE: Read NotePlan files from /noteplan, filter by date, generate embeddings, store in Qdrant

This script:
- Iterates through files in /noteplan directory
- Filters files from the last month
- Generates embeddings using LiteLLM proxy
- Stores embeddings in Qdrant vector database for semantic search
"""

import logging
import os
import sys
from pathlib import Path

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from knowledge_agents.config.api_config import Settings
from knowledge_agents.config.logging_config import setup_logging
from knowledge_agents.dependencies import Dependencies
from knowledge_agents.utils.vector_store_utils import generate_embeddings
from notes.filter import should_skip_file
from notes.parser import read_noteplan_file
from notes.traversal import get_files_from_last_month

# Configure logging using centralized config
setup_logging()
logger = logging.getLogger(__name__)

# NotePlan directory path in container
NOTEPLAN_DIR = Path("/noteplan")


def seed_vector_store_from_noteplan() -> None:
    """Main function to seed the vector store from NotePlan files."""
    logger.info("Starting vector store seeding process from NotePlan files")

    try:
        # Initialize Settings and Dependencies (explicit dependency injection)
        settings = Settings()
        dependencies = Dependencies(settings=settings)
        collection_name = settings.qdrant_collection_name

        # Get files from last month
        files = get_files_from_last_month(NOTEPLAN_DIR)

        if not files:
            logger.warning(
                "No NotePlan files found from the last month. Nothing to seed."
            )
            return

        # Get clients from dependencies
        openai_client = dependencies.proxy_client_manager.get_client()
        qdrant_client = dependencies.vector_store_client_manager.get_client()

        # Get embedding size from settings
        embedding_size = settings.get_embedding_size(
            settings.litellm_proxy_embedding_model
        )

        # Ensure collection exists (using dependencies)
        dependencies.vector_store_client_manager.ensure_collection(
            collection_name=collection_name,
            vector_size=embedding_size,
            recreate=True,  # Recreate to ensure fresh data
        )
        logger.info(
            f"Ensured collection '{collection_name}' exists with vector size {embedding_size}"
        )

        # Read file contents
        file_contents = []
        file_metadata = []

        for file_path, mod_time in files:
            # Defensive check: skip files that should be filtered out
            # (e.g., .DS_Store, files in Caches directories, database files)
            if should_skip_file(file_path):
                logger.debug(f"Skipping filtered file: {file_path}")
                continue

            # Additional safety check: skip database files explicitly
            if file_path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".db-shm", ".db-wal"}:
                logger.debug(f"Skipping database file: {file_path}")
                continue

            try:
                content = read_noteplan_file(file_path)
                # Create a text representation: file path + content
                text_representation = (
                    f"File: {file_path.relative_to(NOTEPLAN_DIR)}\n\n{content}"
                )
                file_contents.append(text_representation)

                file_metadata.append(
                    {
                        "file_path": str(file_path.relative_to(NOTEPLAN_DIR)),
                        "file_name": file_path.name,
                        "modified_at": mod_time.isoformat(),
                        "file_size": len(content),
                    }
                )
                logger.debug(f"Read file: {file_path.name} ({len(content)} chars)")
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                continue

        if not file_contents:
            logger.warning("No file contents to embed. Exiting.")
            return

        logger.info(f"Generating embeddings for {len(file_contents)} files...")

        # Generate embeddings using dependencies
        try:
            embeddings = generate_embeddings(
                texts=file_contents,
                dependencies=dependencies,
                batch_size=10,  # Process in batches
                embedding_model=settings.litellm_proxy_embedding_model,
            )
            logger.info(f"Generated {len(embeddings)} embeddings")
        except Exception as e:
            import traceback
            logger.error(f"Error generating embeddings: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            raise

        # Create points for Qdrant
        points = []
        for idx, (embedding, metadata) in enumerate(zip(embeddings, file_metadata)):
            # Use file path as ID (hash it for uniqueness)
            import hashlib

            point_id = hashlib.md5(metadata["file_path"].encode()).hexdigest()

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=metadata,
                )
            )

        # Upsert points to Qdrant
        logger.info(f"Upserting {len(points)} points to Qdrant...")
        qdrant_client.upsert(collection_name=collection_name, points=points)

        # Verify insertion
        collection_info = qdrant_client.get_collection(collection_name)
        logger.info(
            f"✅ Successfully seeded vector store: {collection_info.points_count} points in collection '{collection_name}'"
        )

    except Exception as e:
        logger.error(f"❌ Error seeding vector store: {e}")
        raise


def main():
    """Entry point for the script."""
    try:
        seed_vector_store_from_noteplan()
        logger.info("Vector store seeding completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

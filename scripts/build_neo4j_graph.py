#!/usr/bin/env python3
"""
Build Neo4j Knowledge Graph from NotePlan Files (Continuous Builder)

PURPOSE: Continuously process NotePlan files and update the knowledge graph in Neo4j
SCOPE: Monitors for new/updated notes and processes them using the graph builder agent

This script:
- Can be run as a continuous service to process new notes
- Uses seed_graph_database.py logic for actual graph building
- Designed to run in a container/service that processes notes as they're added/updated

Note: For initial seeding, use seed_graph_database.py instead.
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

# Import the seeding function to reuse the logic
# Import from sibling script module
import importlib.util
_seed_graph_path = os.path.join(os.path.dirname(__file__), "seed_graph_database.py")
_seed_graph_spec = importlib.util.spec_from_file_location("seed_graph_database", _seed_graph_path)
_seed_graph_module = importlib.util.module_from_spec(_seed_graph_spec)
_seed_graph_spec.loader.exec_module(_seed_graph_module)
seed_graph_database_from_noteplan = _seed_graph_module.seed_graph_database_from_noteplan

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


async def build_neo4j_graph() -> None:
    """
    Main function to build Neo4j knowledge graph from NotePlan files.
    
    This is a wrapper around seed_graph_database_from_noteplan() for continuous building.
    """
    logger.info("Starting Neo4j graph building process (continuous mode)")
    
    # Reuse the seeding logic
    await seed_graph_database_from_noteplan()


def main():
    """Entry point for the script."""
    try:
        asyncio.run(build_neo4j_graph())
        logger.info("Neo4j graph building completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()


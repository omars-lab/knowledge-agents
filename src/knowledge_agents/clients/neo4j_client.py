"""
Neo4j client configuration and management.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from neo4j import GraphDatabase

if TYPE_CHECKING:
    from ..config.api_config import Settings

logger = logging.getLogger(__name__)


class Neo4jClientManager:
    """
    Manages Neo4j database client instances with proper configuration.

    Uses explicit dependency injection - Settings must be provided at initialization.
    This eliminates global state, lazy loading, and the need for monkey-patching.
    """

    def __init__(self, settings: "Settings"):
        """
        Initialize the Neo4j client manager.

        Args:
            settings: Application settings instance (must be provided explicitly)
        """
        self.settings = settings
        self._driver: Optional[GraphDatabase.driver] = None

    def get_driver(self) -> GraphDatabase.driver:
        """Get or create Neo4j driver with proper configuration"""
        if self._driver is None:
            # Get Neo4j connection settings from settings
            uri = self.settings.neo4j_uri
            username = self.settings.neo4j_username
            password = self.settings.neo4j_password

            logger.info(f"Creating Neo4j driver connecting to: {uri} (user: {username})")

            # Create driver with configuration
            self._driver = GraphDatabase.driver(
                uri,
                auth=(username, password),
            )

            # Verify connection
            try:
                self._driver.verify_connectivity()
                logger.info("Successfully connected to Neo4j")
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
                raise

        return self._driver

    def reset_driver(self):
        """Reset the driver (useful for testing or reconfiguration)"""
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def ensure_vector_index(
        self,
        index_name: Optional[str] = None,
        vector_size: Optional[int] = None,
        node_label: str = "Note",
        node_property: str = "embedding",
    ) -> None:
        """
        Ensure a vector index exists, create if it doesn't.

        Args:
            index_name: Name of the vector index (defaults to config value)
            vector_size: Size of vectors (defaults to config value)
            node_label: Label of nodes to index (default: "Note")
            node_property: Property name containing the vector (default: "embedding")
        """
        driver = self.get_driver()
        index_name = index_name or self.settings.neo4j_vector_index_name

        # Use dynamic embedding size based on configured model
        if vector_size is None:
            vector_size = self.settings.get_embedding_size(
                self.settings.litellm_proxy_embedding_model
            )

        with driver.session(database=self.settings.neo4j_database) as session:
            # Check if index exists
            result = session.run(
                """
                SHOW INDEXES
                WHERE name = $index_name
                """,
                index_name=index_name,
            )
            index_exists = result.single() is not None

            if not index_exists:
                logger.info(
                    f"Creating Neo4j vector index '{index_name}' with vector size {vector_size}"
                )

                # Create vector index
                # Note: Neo4j vector index syntax varies by version
                # Try Neo4j 5.x syntax first, fall back to older syntax if needed
                try:
                    # Neo4j 5.x+ syntax
                    session.run(
                        f"""
                        CREATE VECTOR INDEX {index_name} IF NOT EXISTS
                        FOR (n:{node_label})
                        ON n.{node_property}
                        OPTIONS {{
                            indexConfig: {{
                                `vector.dimensions`: {vector_size},
                                `vector.similarity_function`: 'cosine'
                            }}
                        }}
                        """,
                    )
                    logger.info(f"Created vector index '{index_name}' using Neo4j 5.x syntax")
                except Exception as e:
                    logger.warning(f"Failed to create index with Neo4j 5.x syntax: {e}")
                    logger.info("Note: Vector index creation may need to be done manually or via LangChain")
                    # LangChain's Neo4jVector.from_texts will create the index automatically
                    # So we can skip manual creation if it fails
            else:
                logger.info(f"Vector index '{index_name}' already exists")


# NO global instances - created via Dependencies container!
# NO get_neo4j_driver() function - use Dependencies.neo4j_client_manager.get_driver()


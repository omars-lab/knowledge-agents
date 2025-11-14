"""
Vector store test fixtures for Qdrant and OpenAI integration tests.
"""
import hashlib
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
import qdrant_client
from qdrant_client.models import Distance, PointStruct, VectorParams

from knowledge_agents.dependencies import Dependencies
from knowledge_agents.utils.vector_store_utils import generate_embeddings

# Import get_settings inside fixtures to avoid import-time issues with monkey-patching
from notes.parser import read_noteplan_file
from notes.traversal import get_files_from_last_month

logger = logging.getLogger(__name__)

# Test constants
TEST_COLLECTION_NAME = "test_noteplan_files_collection"
EMBEDDING_SIZE = 4096  # Default for qwen3-embedding-8b


@pytest.fixture
def qdrant_client_instance():
    """Create a Qdrant client for testing."""
    return qdrant_client.QdrantClient(host="qdrant", port=6333)


@pytest.fixture
def test_dependencies_for_vector_store(test_dependencies):
    """Provide test dependencies for vector store tests."""
    return test_dependencies


@pytest.fixture
def openai_client(test_dependencies_for_vector_store):
    """Create an OpenAI client for testing using LiteLLM proxy.

    This fixture uses test dependencies to get the proxy client.
    """
    return test_dependencies_for_vector_store.proxy_client_manager.get_client()


@pytest.fixture
def NOTEPLAN_TEST_DIR():
    """Create a temporary directory for NotePlan test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "NotePlan"
        test_dir.mkdir()

        # Create some dummy NotePlan files
        (test_dir / "2025-01-15.md").write_text(
            "# Daily Plan\n- [ ] Go to gym\n- [x] Breakfast\n## Work\n- [ ] Review PRs"
        )
        (test_dir / "Projects" / "MyProject.md").write_text(
            "# Project Alpha\nThis is a project note."
        )
        (test_dir / "Meetings" / "2025-01-14 Meeting.md").write_text(
            "## Meeting Notes\n- Discussed Q4 goals."
        )

        # Create a file modified recently
        recent_file_path = test_dir / "RecentUpdate.md"
        recent_file_path.write_text("# Recent Update\nThis file was modified just now.")
        os.utime(
            recent_file_path, (datetime.now().timestamp(), datetime.now().timestamp())
        )

        yield test_dir


@pytest.fixture
def sample_noteplan_files():
    """Create sample NotePlan file data for testing.
    
    These files are designed to match common test queries:
    - "What are my tasks for today?" -> matches files with "tasks", "today", daily plans
    - "What project ideas do I have?" -> matches files with "project ideas", "ideas"
    """
    return [
        {
            "file_path": "2025-01-15.md",
            "file_name": "2025-01-15.md",
            "content": "# Daily Plan for Today\n\n## Morning Tasks\n- [ ] Go to gym\n- [x] Breakfast\n\n## Work Tasks\n- [ ] Review PRs\n- [x] Standup meeting\n\nThese are my tasks for today.",
            "modified_at": "2025-01-15T08:00:00",
            "file_size": 180,
        },
        {
            "file_path": "Projects/ideas.md",
            "file_name": "ideas.md",
            "content": "# Project Ideas\n\nHere are my project ideas:\n\n## AI Projects\n- [ ] Build chatbot\n- [ ] ML model training\n\n## Automation\n- [ ] CI/CD pipeline\n\nThese are all the project ideas I have.",
            "modified_at": "2024-01-14T10:00:00",
            "file_size": 150,
        },
        {
            "file_path": "2025-01-15-tasks.md",
            "file_name": "2025-01-15-tasks.md",
            "content": "# Tasks for Today\n\nMy tasks for today include:\n\n## Morning\n- [ ] Go to gym\n- [x] Breakfast\n\n## Work\n- [ ] Review PRs\n- [x] Standup meeting\n\nThese are all my tasks for today.",
            "modified_at": "2025-01-15T08:00:00",
            "file_size": 180,
        },
    ]


@pytest.fixture
def cleanup_collection(qdrant_client_instance):
    """Clean up test collection before and after tests."""
    # Clean up before test
    try:
        qdrant_client_instance.delete_collection(TEST_COLLECTION_NAME)
    except Exception:
        pass  # Collection doesn't exist, which is fine

    yield

    # Clean up after test
    try:
        qdrant_client_instance.delete_collection(TEST_COLLECTION_NAME)
    except Exception:
        pass  # Already deleted or doesn't exist


@pytest.fixture
def seeded_noteplan_collection(
    qdrant_client_instance,
    test_dependencies_for_vector_store,
    sample_noteplan_files,
    cleanup_collection,
):
    """Create a collection with seeded NotePlan file vectors."""
    # Get settings from test dependencies
    settings = test_dependencies_for_vector_store.settings
    embedding_model = settings.litellm_proxy_embedding_model
    embedding_size = settings.get_embedding_size(embedding_model)

    # Get OpenAI client from dependencies
    openai_client = test_dependencies_for_vector_store.proxy_client_manager.get_client()

    # Create collection with correct vector size
    qdrant_client_instance.create_collection(
        collection_name=TEST_COLLECTION_NAME,
        vectors_config=VectorParams(
            size=embedding_size,
            distance=Distance.COSINE,
        ),
    )

    # Prepare text representations
    file_contents = []
    file_metadata = []
    for file_data in sample_noteplan_files:
        text = f"File: {file_data['file_path']}\n\n{file_data['content']}"
        file_contents.append(text)
        file_metadata.append(
            {
                "file_path": file_data["file_path"],
                "file_name": file_data["file_name"],
                "modified_at": file_data["modified_at"],
                "file_size": file_data["file_size"],
            }
        )

    # Generate embeddings using dependencies
    embeddings = generate_embeddings(
        texts=file_contents,
        dependencies=test_dependencies_for_vector_store,
        batch_size=10,
        embedding_model=embedding_model,
    )

    # Create points
    points = []
    for embedding, metadata in zip(embeddings, file_metadata):
        point_id = hashlib.md5(metadata["file_path"].encode()).hexdigest()

        points.append(
            PointStruct(
                id=point_id,
                vector=embedding,
                payload=metadata,
            )
        )

    # Insert points
    qdrant_client_instance.upsert(collection_name=TEST_COLLECTION_NAME, points=points)

    yield TEST_COLLECTION_NAME

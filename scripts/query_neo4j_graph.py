#!/usr/bin/env python3
"""
Query Neo4j Knowledge Graph for Note Questions

PURPOSE: Answer questions about notes using Neo4j graph and vector search
SCOPE: Combines vector search with graph patterns to provide contextual answers

This script:
- Performs vector search to find relevant notes
- Uses graph patterns to find related entities and relationships
- Uses LLM to synthesize answers from graph context
"""

import asyncio
import logging
import os
import sys
from typing import List, Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from knowledge_agents.config.api_config import Settings
from knowledge_agents.config.logging_config import setup_logging
from knowledge_agents.dependencies import Dependencies
from knowledge_agents.clients.neo4j_client import Neo4jClientManager

# Neo4j and LangChain imports
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores.neo4j_vector import Neo4jVector
from langchain.graphs import Neo4jGraph
from langchain.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnableLambda
from openai import AsyncOpenAI

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


class ProxyEmbeddings(OpenAIEmbeddings):
    """Custom embeddings class that uses LiteLLM proxy instead of direct OpenAI."""

    def __init__(self, proxy_base_url: str, api_key: str, model: str, **kwargs):
        api_url = f"{proxy_base_url}/v1"
        super().__init__(
            openai_api_base=api_url,
            openai_api_key=api_key,
            model=model,
            **kwargs
        )


async def query_neo4j_graph(
    question: str,
    dependencies: Dependencies,
    max_results: int = 5,
) -> str:
    """
    Query Neo4j graph to answer a question about notes.
    
    Args:
        question: User's question
        dependencies: Dependencies container
        max_results: Maximum number of results to return
        
    Returns:
        Answer to the question
    """
    settings = dependencies.settings
    
    # Get Neo4j driver
    neo4j_manager = Neo4jClientManager(settings=settings)
    driver = neo4j_manager.get_driver()
    
    # Create embeddings using proxy
    proxy_base_url = f"http://{settings.litellm_proxy_host}:{settings.litellm_proxy_port}"
    embedding_model = ProxyEmbeddings(
        proxy_base_url=proxy_base_url,
        api_key=settings.openai_api_key or "",
        model=settings.litellm_proxy_embedding_model,
    )
    
    # Create Neo4jVector for vector search
    try:
        vector_store = Neo4jVector.from_existing_index(
            embedding=embedding_model,
            url=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
            database=settings.neo4j_database,
            index_name=settings.neo4j_vector_index_name,
        )
    except Exception as e:
        logger.error(f"Error creating vector store: {e}")
        logger.info("Vector index may not exist. Run seed_neo4j_vector_store.py first.")
        raise
    
    # Perform vector search
    logger.info(f"Performing vector search for: {question}")
    vector_results = vector_store.similarity_search(question, k=max_results)
    
    # Extract relevant note paths from vector search
    note_paths = []
    for doc in vector_results:
        # Extract file_path from metadata if available
        if hasattr(doc, 'metadata') and 'file_path' in doc.metadata:
            note_paths.append(doc.metadata['file_path'])
        # Or try to extract from page_content
        elif 'File:' in doc.page_content:
            note_paths.append(doc.page_content.split('\n')[0].replace('File: ', ''))
    
    logger.info(f"Found {len(note_paths)} relevant notes: {note_paths}")
    
    # Use graph patterns to find related entities
    graph = Neo4jGraph(
        url=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
    
    # Query for entities related to the found notes
    related_entities_query = """
    MATCH (n:Note)
    WHERE n.file_path IN $note_paths
    MATCH (n)-[:CONTAINS]->(e:Entity)
    OPTIONAL MATCH (e)-[r]-(related:Entity)
    RETURN DISTINCT e.name as entity, 
           labels(e)[0] as entity_type,
           type(r) as relationship,
           related.name as related_entity,
           labels(related)[0] as related_type
    LIMIT 50
    """
    
    with driver.session(database=settings.neo4j_database) as session:
        result = session.run(related_entities_query, note_paths=note_paths)
        graph_context = []
        for record in result:
            graph_context.append({
                "entity": record["entity"],
                "entity_type": record["entity_type"],
                "relationship": record["relationship"],
                "related_entity": record["related_entity"],
                "related_type": record["related_type"],
            })
    
    logger.info(f"Found {len(graph_context)} related entities in graph")
    
    # Build context for LLM
    vector_context = "\n\n".join([doc.page_content for doc in vector_results])
    
    graph_context_str = "\n".join([
        f"- {ctx['entity']} ({ctx['entity_type']}) "
        f"{ctx['relationship']} {ctx['related_entity']} ({ctx['related_type']})"
        if ctx['related_entity'] else f"- {ctx['entity']} ({ctx['entity_type']})"
        for ctx in graph_context[:20]  # Limit to top 20
    ])
    
    # Create prompt for LLM
    prompt_template = PromptTemplate.from_template("""
You are a helpful assistant that answers questions about the user's personal notes using both vector search results and knowledge graph context.

## Question
{question}

## Relevant Notes (from vector search)
{vector_context}

## Related Entities and Relationships (from knowledge graph)
{graph_context}

## Instructions
1. Use the relevant notes to understand the context
2. Use the knowledge graph to find connections and relationships
3. Synthesize information from both sources to provide a comprehensive answer
4. Reference specific notes and entities when relevant
5. If information is not available, clearly state that

## Answer
""")
    
    prompt = prompt_template.format(
        question=question,
        vector_context=vector_context[:3000],  # Limit context size
        graph_context=graph_context_str,
    )
    
    # Get LLM response
    client = dependencies.openai_client_manager.get_client()
    
    response = await client.chat.completions.create(
        model=settings.litellm_proxy_completion_model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that answers questions about personal notes using knowledge graphs."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=1000,
    )
    
    answer = response.choices[0].message.content
    
    return answer


async def interactive_query_loop(dependencies: Dependencies) -> None:
    """Interactive loop for querying the graph."""
    print("\n" + "="*60)
    print("Neo4j Graph Query Interface")
    print("="*60)
    print("Type your questions about your notes. Type 'exit' to quit.\n")
    
    while True:
        try:
            question = input("Question: ").strip()
            
            if question.lower() in ['exit', 'quit', 'q']:
                print("Goodbye!")
                break
            
            if not question:
                continue
            
            print("\nThinking...")
            answer = await query_neo4j_graph(question, dependencies)
            print(f"\nAnswer: {answer}\n")
            print("-"*60 + "\n")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"Error processing question: {e}", exc_info=True)
            print(f"\nError: {e}\n")


def main():
    """Entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Query Neo4j knowledge graph for note questions")
    parser.add_argument(
        "--question",
        type=str,
        help="Question to ask (if not provided, starts interactive mode)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximum number of vector search results (default: 5)",
    )
    
    args = parser.parse_args()
    
    try:
        settings = Settings()
        dependencies = Dependencies(settings=settings)
        
        if args.question:
            # Single question mode
            answer = asyncio.run(
                query_neo4j_graph(args.question, dependencies, args.max_results)
            )
            print(f"\nQuestion: {args.question}")
            print(f"Answer: {answer}\n")
        else:
            # Interactive mode
            asyncio.run(interactive_query_loop(dependencies))
        
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()


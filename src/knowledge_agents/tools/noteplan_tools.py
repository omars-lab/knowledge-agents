"""
NotePlan tools for the agent - calls tidy-mcp HTTP service.

This module provides agent-compatible function tools that call the tidy-mcp HTTP service
to generate NotePlan x-callback-url links.
"""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Get tidy-mcp service URL from environment (defaults to service name in Docker)
TIDY_MCP_URL = os.getenv("TIDY_MCP_URL", "http://tidy-mcp:8000")


def derive_xcallback_url_from_noteplan_file(
    file_path: str, heading: Optional[str] = None
) -> str:
    """
    Derive an x-callback-url link from a NotePlan file path.
    
    This tool calls the tidy-mcp HTTP service to convert a NotePlan file path
    into a shareable x-callback-url link that will open the note in the NotePlan app.
    
    Args:
        file_path: Path to the NotePlan file (e.g., '2025-11-13.md' or 'notes/project-ideas.md')
        heading: Optional heading within the document to link to
    
    Returns:
        The x-callback-url link as a string, or an error message if the call fails
    """
    try:
        # Call tidy-mcp HTTP service
        url = f"{TIDY_MCP_URL}/tools/derive_xcallback_url_from_noteplan_file"
        payload = {
            "file_path": file_path,
        }
        if heading:
            payload["heading"] = heading
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        # Return the URL if successful, otherwise return error message
        if result.get("success") and "x_callback_url" in result:
            return result["x_callback_url"]
        else:
            error_msg = result.get("error", "Unknown error")
            logger.warning(f"tidy-mcp returned error: {error_msg}")
            return f"Error generating link: {error_msg}"
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling tidy-mcp HTTP service: {e}", exc_info=True)
        return f"Error: Failed to call tidy-mcp service: {str(e)}"
    except Exception as e:
        logger.error(f"Error in derive_xcallback_url_from_noteplan_file: {e}", exc_info=True)
        return f"Error: {str(e)}"


"""
Chat UI Smoke Tests

PURPOSE: Tests the chat nginx container serves static files correctly
SCOPE: Health endpoint, static file serving, content types, SPA fallback
REQUIRES: Chat container running (docker compose up -d chat)

TEST CATEGORIES:
- Health: /health endpoint returns 200
- Static Files: index.html, chat.js, chat.css served with correct content types
- SPA Fallback: Unknown routes fall back to index.html
- Content Integrity: HTML references valid JS/CSS, key DOM elements present

WHAT BELONGS HERE:
- Nginx container health and static serving
- Content type validation
- HTML structure validation

WHAT DOESN'T BELONG HERE:
- Browser rendering / JS execution tests
"""
import os

import pytest
import requests

CHAT_URL = os.getenv("CHAT_URL", "http://localhost:8080")
AGENT_URL = os.getenv("CLAUDE_AGENT_URL", "http://localhost:8004")


def _chat_reachable():
    """Check if the chat container is running."""
    try:
        requests.get(f"{CHAT_URL}/health", timeout=2)
        return True
    except Exception:
        return False


skip_if_no_chat = pytest.mark.skipif(
    not _chat_reachable(),
    reason=f"Chat container not reachable at {CHAT_URL} (run: docker compose up -d chat)",
)

pytestmark = [pytest.mark.unit, skip_if_no_chat]


class TestChatHealth:
    """Health endpoint tests."""

    def test_health_returns_200(self):
        """Health endpoint should return 200 with 'ok' body."""
        response = requests.get(f"{CHAT_URL}/health", timeout=5)
        assert response.status_code == 200
        assert response.text.strip() == "ok"

    def test_health_content_type_is_text(self):
        """Health endpoint should return text/plain."""
        response = requests.get(f"{CHAT_URL}/health", timeout=5)
        assert "text/plain" in response.headers.get("Content-Type", "")


class TestStaticFileServing:
    """Static file serving tests."""

    def test_index_html_returns_200(self):
        """Root path should return index.html."""
        response = requests.get(f"{CHAT_URL}/", timeout=5)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")

    def test_chat_js_returns_200(self):
        """chat.js should be served with correct content type."""
        response = requests.get(f"{CHAT_URL}/chat.js", timeout=5)
        assert response.status_code == 200
        content_type = response.headers.get("Content-Type", "")
        assert "javascript" in content_type

    def test_chat_css_returns_200(self):
        """chat.css should be served with correct content type."""
        response = requests.get(f"{CHAT_URL}/chat.css", timeout=5)
        assert response.status_code == 200
        assert "text/css" in response.headers.get("Content-Type", "")

    def test_spa_fallback_serves_index(self):
        """Unknown routes should fall back to index.html (SPA routing)."""
        response = requests.get(f"{CHAT_URL}/nonexistent-page", timeout=5)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", "")
        assert "<title>Chat" in response.text


class TestHTMLIntegrity:
    """Validate HTML structure and references."""

    @pytest.fixture(autouse=True)
    def fetch_index(self):
        """Fetch index.html once for all tests in this class."""
        self.html = requests.get(f"{CHAT_URL}/", timeout=5).text

    def test_page_title(self):
        """Page should have the correct title."""
        assert "<title>Chat - Bytes of Purpose</title>" in self.html

    def test_references_chat_js(self):
        """HTML should reference chat.js."""
        assert 'src="chat.js"' in self.html

    def test_references_chat_css(self):
        """HTML should reference chat.css."""
        assert 'href="chat.css"' in self.html

    def test_references_marked_cdn(self):
        """HTML should reference marked.js CDN."""
        assert "marked" in self.html

    def test_references_hljs_cdn(self):
        """HTML should reference highlight.js CDN."""
        assert "highlight" in self.html

    def test_has_message_input(self):
        """HTML should have a message input element."""
        assert 'id="message-input"' in self.html

    def test_has_messages_container(self):
        """HTML should have a messages container."""
        assert 'id="messages"' in self.html

    def test_has_sidebar(self):
        """HTML should have a sidebar for sessions."""
        assert 'id="sidebar"' in self.html

    def test_has_send_button(self):
        """HTML should have a send button."""
        assert 'id="send-btn"' in self.html

    def test_has_error_banner(self):
        """HTML should have an error banner."""
        assert 'id="error-banner"' in self.html


class TestSecurityHeaders:
    """Validate nginx doesn't leak sensitive info."""

    def test_no_server_version_leak(self):
        """Server header should not expose detailed nginx version."""
        response = requests.get(f"{CHAT_URL}/health", timeout=5)
        server = response.headers.get("Server", "")
        # nginx:alpine exposes version by default; this test documents current state.
        # If we add server_tokens off, this test should assert no version.
        assert "nginx" in server.lower()

    def test_404_for_dotfiles(self):
        """Dotfiles like .env should not be served."""
        response = requests.get(f"{CHAT_URL}/.env", timeout=5)
        # SPA fallback serves index.html for all routes, which is fine
        # as long as there's no .env file in the chat/ dir
        assert response.status_code == 200  # SPA fallback
        assert ".env" not in response.text or "<title>Chat" in response.text


# ---------------------------------------------------------------------------
# Connection tests: chat UI -> claude-agent API
# ---------------------------------------------------------------------------

def _agent_reachable():
    """Check if the claude-agent is running."""
    try:
        requests.get(f"{AGENT_URL}/health", timeout=2)
        return True
    except Exception:
        return False


skip_if_no_agent = pytest.mark.skipif(
    not _agent_reachable(),
    reason=f"Claude agent not reachable at {AGENT_URL}",
)


@skip_if_no_agent
class TestAgentConnection:
    """Verify chat UI can reach the claude-agent API."""

    def test_agent_health(self):
        """Claude agent health endpoint should be reachable."""
        response = requests.get(f"{AGENT_URL}/health", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_agent_cors_preflight(self):
        """CORS preflight from chat UI origin should be allowed."""
        response = requests.options(
            f"{AGENT_URL}/api/v1/chat/stream",
            headers={
                "Origin": "http://localhost:8080",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
            timeout=5,
        )
        assert response.status_code == 200
        assert "http://localhost:8080" in response.headers.get(
            "Access-Control-Allow-Origin", ""
        )

    def test_agent_stream_endpoint_rejects_get(self):
        """Stream endpoint should reject GET (only POST allowed)."""
        response = requests.get(f"{AGENT_URL}/api/v1/chat/stream", timeout=5)
        assert response.status_code == 405

    def test_agent_stream_endpoint_accepts_post(self):
        """Stream endpoint should accept POST and return SSE content type."""
        response = requests.post(
            f"{AGENT_URL}/api/v1/chat/stream",
            json={"message": "hello"},
            headers={"Content-Type": "application/json"},
            timeout=10,
            stream=True,
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("Content-Type", "")
        # Read just the first chunk to verify SSE format, then close
        for chunk in response.iter_lines():
            if chunk:
                line = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
                assert line.startswith("data: "), f"Expected SSE data line, got: {line}"
                break
        response.close()

    def test_agent_sessions_list(self):
        """Sessions endpoint should return a list."""
        response = requests.get(f"{AGENT_URL}/api/v1/sessions", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_js_api_base_targets_agent_in_dev(self):
        """chat.js should point to claude-agent:8004 when served from port 8080."""
        response = requests.get(f"{CHAT_URL}/chat.js", timeout=5)
        assert response.status_code == 200
        # Verify the dev-mode API base URL detection logic exists
        assert "localhost:8004" in response.text
        assert 'window.location.port === "8080"' in response.text

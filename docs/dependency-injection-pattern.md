# Dependency Injection Pattern

## Problem

Current codebase has multiple issues:
- **Lazy loading**: Settings loaded on-demand, making it hard to track dependencies
- **Global state**: `get_settings()` returns cached global instance
- **Monkey-patching**: Tests need to monkey-patch `get_settings()` to inject test keys
- **Hidden dependencies**: Functions call `get_settings()` internally, making dependencies unclear
- **Circular import risks**: Module-level imports can cause circular dependencies

## Solution: Explicit Dependency Injection

### Pattern Overview

1. **Dependencies Container**: Single `Dependencies` class holds all app dependencies
2. **Explicit Constructors**: All clients accept `Settings` in constructor
3. **Top-level Imports**: Use `TYPE_CHECKING` guards for type hints only
4. **No Global State**: Dependencies passed explicitly, no lazy loading
5. **Test-Friendly**: Create test `Dependencies` with test `Settings`, no monkey-patching

### Example: Before vs After

#### Before (Current - Complex)
```python
# proxy_client.py
from ..config import api_config

class ProxyClientManager:
    def __init__(self):
        self._client = None
    
    def _get_settings(self):
        return api_config.get_settings()  # Lazy loading, global state
    
    def get_client(self):
        settings = self._get_settings()  # Hidden dependency
        api_key = settings.openai_api_key
        # ... create client

# Tests need monkey-patching
def inject_test_api_key():
    original = api_config.get_settings
    api_config.get_settings = lambda: test_settings  # Monkey-patch!
```

#### After (DI Pattern - Simple)
```python
# proxy_client.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.api_config import Settings

class ProxyClientManager:
    def __init__(self, settings: Settings):  # Explicit dependency
        self.settings = settings  # Stored, no lazy loading
        self._client = None
    
    def get_client(self):
        api_key = self.settings.openai_api_key  # Direct access
        # ... create client

# Tests - clean and explicit
def test_with_dependencies():
    test_settings = Settings(openai_api_key="sk-test")
    manager = ProxyClientManager(settings=test_settings)  # Explicit!
```

### Architecture

```
┌─────────────────┐
│   Settings      │  (Loaded once at startup)
│   - API keys    │
│   - Config      │
└────────┬────────┘
         │
         │ injected into
         ▼
┌─────────────────┐
│  Dependencies   │  (Container)
│  - settings     │
│  - clients      │
└────────┬────────┘
         │
         │ passed to
         ▼
┌─────────────────┐
│   Services      │
│   - Agents      │
│   - Routers     │
└─────────────────┘
```

### Implementation Steps

1. **Create Dependencies Container** (`dependencies.py`)
   - Holds Settings instance
   - Creates client managers with Settings
   - Provides accessors for all dependencies

2. **Refactor Clients** (accept Settings in constructor)
   - `ProxyClientManager(settings: Settings)`
   - `OpenAIClientManager(settings: Settings)`
   - `VectorStoreClientManager(settings: Settings)`

3. **Update Main App** (`main.py`)
   - Initialize Settings once at startup
   - Create Dependencies container
   - Pass Dependencies to routers/services

4. **Update Routers/Services** (accept Dependencies)
   - `NoteQueryService(deps: Dependencies)`
   - Routers get Dependencies from FastAPI dependency injection

5. **Update Tests** (create test Dependencies)
   - No monkey-patching needed
   - Create test Settings with test API key
   - Create test Dependencies
   - Pass explicitly to components

### Benefits

✅ **No Lazy Loading**: All dependencies initialized at startup
✅ **No Global State**: Dependencies passed explicitly
✅ **No Monkey-Patching**: Tests create test instances
✅ **Clear Dependencies**: Constructor shows what's needed
✅ **Top-Level Imports**: `TYPE_CHECKING` avoids circular deps
✅ **Easy Testing**: Create test instances with test config

### Migration Strategy

1. Create `dependencies.py` (new file)
2. Refactor one client at a time (e.g., `ProxyClientManager`)
3. Update code that uses that client
4. Update tests for that client
5. Repeat for other clients
6. Remove old `get_settings()` global accessor

### FastAPI Integration

```python
# main.py
from .dependencies import initialize_dependencies, Dependencies
from .config.api_config import Settings

@app.on_event("startup")
async def startup():
    settings = Settings()  # Load once
    deps = initialize_dependencies(settings)  # Initialize container

# router.py
from fastapi import Depends
from ..dependencies import get_dependencies

@router.get("/endpoint")
async def endpoint(deps: Dependencies = Depends(get_dependencies)):
    client = deps.proxy_client_manager.get_client()
    # ...
```

### Testing Pattern

```python
# conftest.py
@pytest.fixture
def test_dependencies():
    """Create test dependencies with test API key."""
    test_settings = Settings(
        openai_api_key="sk-test-key",
        environment="test"
    )
    return Dependencies(settings=test_settings)

# test_agent.py
def test_agent(test_dependencies):
    agent = NoteQueryAgent(dependencies=test_dependencies)
    # No monkey-patching needed!
```


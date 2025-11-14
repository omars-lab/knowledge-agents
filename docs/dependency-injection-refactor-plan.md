# Dependency Injection Refactor Plan

## Complete Example: ProxyClientManager (Before → After)

### Before (Current - Complex)
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

# Global instance
_proxy_client_manager = ProxyClientManager()

def get_proxy_client():
    return _proxy_client_manager.get_client()
```

### After (DI Pattern - Simple)
```python
# proxy_client.py
from typing import TYPE_CHECKING, Optional
from openai import OpenAI, AsyncOpenAI

if TYPE_CHECKING:
    from ..config.api_config import Settings

class ProxyClientManager:
    def __init__(self, settings: Settings):  # Explicit dependency
        self.settings = settings  # Stored, no lazy loading
        self._client: Optional[OpenAI] = None
        self._async_client: Optional[AsyncOpenAI] = None
        self._last_base_url: Optional[str] = None
        self._last_api_key: Optional[str] = None
    
    def _get_proxy_base_url(self) -> str:
        host = os.getenv("LITELLM_PROXY_HOST", self.settings.litellm_proxy_host)
        port = os.getenv("LITELLM_PROXY_PORT", str(self.settings.litellm_proxy_port))
        return f"http://{host}:{port}"
    
    def get_client(self) -> OpenAI:
        if self._client is None:
            api_key = self.settings.openai_api_key  # Direct access
            if not api_key:
                raise ValueError("OpenAI API key is required")
            # ... create client
        return self._client

# NO global instance - created via Dependencies container
```

## Complete Catalog of Files to Update

### Category 1: Core Client Managers (Must Refactor First)

1. **`src/knowledge_agents/clients/proxy_client.py`**
   - ✅ Already started - constructor accepts Settings
   - ❌ Remove `_get_settings()` method
   - ❌ Remove global `_proxy_client_manager` instance
   - ❌ Remove `get_proxy_client()`, `get_proxy_async_client()`, `reset_proxy_clients()` functions
   - ✅ Update `get_client()` and `get_async_client()` to use `self.settings`
   - ✅ Update `_get_proxy_base_url()` to use `self.settings`

2. **`src/knowledge_agents/clients/openai.py`**
   - ❌ Add `settings: Settings` parameter to `__init__`
   - ❌ Remove `_get_settings()` method
   - ❌ Remove global `_client_manager` instance
   - ❌ Remove `get_openai_client()`, `reset_openai_client()` functions
   - ❌ Update `get_client()` to use `self.settings`

3. **`src/knowledge_agents/clients/vector_store.py`**
   - ❌ Add `settings: Settings` parameter to `__init__`
   - ❌ Remove `_get_settings()` method
   - ❌ Remove global `_client_manager` instance
   - ❌ Remove `get_vector_store_client()`, `reset_vector_store_client()`, `ensure_vector_store_collection()` functions
   - ❌ Update `get_client()` and `ensure_collection()` to use `self.settings`

4. **`src/knowledge_agents/clients/__init__.py`**
   - ❌ Remove all `get_*_client()` exports
   - ✅ Keep only class exports (or remove entirely if using Dependencies)

### Category 2: Dependencies Container (New/Update)

5. **`src/knowledge_agents/dependencies.py`**
   - ✅ Already created
   - ❌ Update `Dependencies` class to properly initialize all client managers
   - ❌ Add `openai_client_manager` property
   - ❌ Ensure all clients are created with Settings from container

### Category 3: Utilities and Helpers

6. **`src/knowledge_agents/utils/model_utils.py`**
   - ❌ Change `get_default_litellm_model()` to accept `settings: Settings` parameter
   - ❌ Remove `get_settings()` call
   - ❌ Remove `get_openai_api_key()` call (use `settings.openai_api_key`)

7. **`src/knowledge_agents/utils/vector_store_utils.py`**
   - ❌ Change `generate_embeddings()` to accept `settings: Settings` parameter OR `dependencies: Dependencies`
   - ❌ Remove `get_proxy_client()` call (should be passed in)
   - ❌ Update to use passed-in client or get from dependencies

8. **`src/knowledge_agents/database/queries/query_vector_store.py`**
   - ❌ Change `VectorStoreQueries.__init__()` to accept `dependencies: Dependencies` OR `settings: Settings`
   - ❌ Remove `get_proxy_client()` and `get_vector_store_client()` calls
   - ❌ Remove `get_settings()` call
   - ❌ Get clients from dependencies or construct with settings

### Category 4: Services and Agents

9. **`src/knowledge_agents/services/note_query_service.py`**
   - ❌ Add `dependencies: Dependencies` parameter to `__init__`
   - ❌ Pass dependencies to `run_note_query_agent()` or update agent to use dependencies

10. **`src/knowledge_agents/agents/note_query_agent.py`**
    - ❌ Change `run_note_query_agent()` to accept `dependencies: Dependencies` parameter
    - ❌ Remove `get_settings()` calls
    - ❌ Remove `get_default_litellm_model()` call (get model from dependencies)
    - ❌ Update `VectorStoreQueries` instantiation to use dependencies
    - ❌ Update guardrail creation to use dependencies

11. **`src/knowledge_agents/guardrails/input/note_query_guardrail.py`**
    - ❌ Change `get_note_query_guardrail_agent()` to accept `settings: Settings` parameter
    - ❌ Remove `get_settings()` call
    - ❌ Update `get_default_litellm_model()` call to pass settings

12. **`src/knowledge_agents/guardrails/output/judge_note_answer_guardrail.py`**
    - ❌ Similar changes to input guardrail

### Category 5: Routers and API Layer

13. **`src/knowledge_agents/routers/note_query.py`**
    - ❌ Add FastAPI dependency for `Dependencies`
    - ❌ Update `NoteQueryService` instantiation to pass dependencies
    - ❌ Use FastAPI's `Depends(get_dependencies)`

14. **`src/knowledge_agents/routers/base.py`**
    - ❌ Check if it uses any clients/settings - update if needed

15. **`src/knowledge_agents/main.py`**
    - ❌ Initialize `Dependencies` in `startup_event()`
    - ❌ Call `initialize_dependencies(settings)`
    - ❌ Update to use dependencies where needed

16. **`src/knowledge_agents/startup.py`**
    - ❌ Update `startup_tasks()` to accept `dependencies: Dependencies`
    - ❌ Remove `get_openai_client()` call
    - ❌ Use `dependencies.openai_client` instead

17. **`src/knowledge_agents/utils/exception_handlers.py`**
    - ❌ Check if it uses `get_settings()` - update if needed

### Category 6: Configuration

18. **`src/knowledge_agents/config/api_config.py`**
    - ❌ Keep `Settings` class (unchanged)
    - ❌ Keep `get_settings()` for backward compatibility (mark as deprecated)
    - ❌ Consider removing `settings` global instance (or keep for backward compat)
    - ❌ Remove `reset_settings()` or keep for backward compat

19. **`src/knowledge_agents/config/secrets_config.py`**
    - ✅ Mostly fine - just used by Settings.__init__()
    - ❌ No changes needed

20. **`src/knowledge_agents/database/sessions.py`**
    - ❌ Currently imports `settings` from `api_config` - needs to accept Settings
    - ❌ Change `get_database_url()` and related functions to accept `settings: Settings`

### Category 7: Scripts

21. **`scripts/seed_vector_store.py`**
    - ❌ Create Settings instance at script start
    - ❌ Create Dependencies with Settings
    - ❌ Use dependencies instead of `get_proxy_client()`, `get_vector_store_client()`

22. **`scripts/seed_database.py`**
    - ❌ Check if it uses any clients - update if needed

23. **`scripts/call_litellm_model.py`**
    - ❌ Check if it uses any clients - update if needed

### Category 8: Tests

24. **`tst/integration/fixtures/litellm_api_key.py`**
    - ❌ Remove monkey-patching logic
    - ❌ Create test `Settings` instance with test API key
    - ❌ Create test `Dependencies` instance
    - ❌ Return test dependencies

25. **`tst/integration/fixtures/vector_store.py`**
    - ❌ Update `openai_client` fixture to use test dependencies
    - ❌ Remove `get_proxy_client()` call
    - ❌ Remove `inject_test_api_key` dependency (no longer needed)

26. **`tst/integration/fixtures/agents_client.py`**
    - ❌ Update to use test dependencies instead of setting default client

27. **`tst/integration/database/test_vector_store.py`**
    - ❌ Update to use test dependencies

28. **`tst/conftest.py`**
    - ❌ Add test dependencies fixture
    - ❌ Update any other fixtures that use clients

### Category 9: Documentation

29. **`docs/dependency-injection-pattern.md`**
    - ✅ Already created

30. **`DEVELOPMENT.md`**
    - ❌ Update to document new dependency injection pattern
    - ❌ Remove old monkey-patching documentation
    - ❌ Add examples of using dependencies in tests

## Migration Order (Recommended)

1. **Phase 1: Core Infrastructure**
   - Complete `dependencies.py`
   - Refactor `ProxyClientManager` (already started)
   - Refactor `OpenAIClientManager`
   - Refactor `VectorStoreClientManager`

2. **Phase 2: Utilities**
   - Refactor `model_utils.py`
   - Refactor `vector_store_utils.py`
   - Refactor `query_vector_store.py`

3. **Phase 3: Services & Agents**
   - Refactor `note_query_agent.py`
   - Refactor guardrails
   - Refactor `note_query_service.py`

4. **Phase 4: API Layer**
   - Update `main.py` to initialize dependencies
   - Update `startup.py`
   - Update routers

5. **Phase 5: Scripts & Database**
   - Update scripts
   - Update `database/sessions.py`

6. **Phase 6: Tests**
   - Update test fixtures
   - Update all tests to use test dependencies

7. **Phase 7: Cleanup**
   - Remove deprecated `get_*_client()` functions
   - Remove global instances
   - Update documentation

## Key Principles

1. **No Lazy Loading**: All dependencies initialized at startup
2. **No Global State**: Dependencies passed explicitly
3. **No Monkey-Patching**: Tests create test instances
4. **Clear Dependencies**: Constructor shows what's needed
5. **Top-Level Imports**: Use `TYPE_CHECKING` for type hints only
6. **Explicit is Better**: Pass dependencies explicitly, don't fetch from globals


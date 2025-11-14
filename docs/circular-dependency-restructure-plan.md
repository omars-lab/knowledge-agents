# Circular Dependency Restructure Plan

## Problem Analysis

Current circular dependency issues:

1. **`dependencies.py`**: Lazy imports in properties because:
   - `Dependencies` → imports `Settings` (TYPE_CHECKING)
   - `Dependencies` → imports client managers (TYPE_CHECKING)
   - Client managers → import `Settings` (TYPE_CHECKING)
   - If we import clients at module level, potential cycle

2. **`database/sessions.py`**: Fallback imports because:
   - May be imported before `dependencies` is initialized
   - Uses `get_dependencies()` which requires initialization

3. **Guardrails**: Fallback imports for backward compatibility:
   - May be called before dependencies initialized
   - Use `get_dependencies()` or `get_settings()`

## Solution: Multi-Layer Architecture

### Layer 1: Pure Types (No Dependencies)
- `Settings` - Configuration only
- Type definitions (`Note`, `Response`, etc.)

### Layer 2: Client Managers (Only depend on Settings)
- `ProxyClientManager(settings: Settings)`
- `OpenAIClientManager(settings: Settings)`
- `VectorStoreClientManager(settings: Settings)`

### Layer 3: Dependencies Container (Depends on Settings + Clients)
- `Dependencies(settings: Settings)` - Eagerly initializes all clients
- No lazy loading, no circular dependencies

### Layer 4: Services/Agents/Guardrails (Depends on Dependencies)
- Receive `Settings` or `Dependencies` explicitly
- No global accessors

### Layer 5: Routers/API (Depends on Services)
- FastAPI dependency injection
- Pass dependencies explicitly

## Implementation Strategy

### Step 1: Eager Initialization in Dependencies

**Current (lazy loading):**
```python
@property
def proxy_client_manager(self) -> ProxyClientManager:
    if self._proxy_client_manager is None:
        from .clients.proxy_client import ProxyClientManager  # Lazy import
        self._proxy_client_manager = ProxyClientManager(settings=self.settings)
    return self._proxy_client_manager
```

**New (eager initialization):**
```python
def __init__(self, settings: Settings):
    self.settings = settings
    # Eagerly initialize all clients - no lazy loading
    # Use late imports only to break potential cycles
    from .clients.proxy_client import ProxyClientManager
    from .clients.vector_store import VectorStoreClientManager
    from .clients.openai import OpenAIClientManager
    
    self._proxy_client_manager = ProxyClientManager(settings=settings)
    self._vector_store_client_manager = VectorStoreClientManager(settings=settings)
    self._openai_client_manager = OpenAIClientManager(settings=settings)
```

**Why this works:**
- Client managers only depend on `Settings` (no circular dependency)
- `Dependencies` depends on `Settings` and client managers (no cycle)
- Late imports in `__init__` are safe because:
  - `__init__` is called at runtime, not import time
  - All dependencies are already imported
  - No circular import risk

### Step 2: Remove Fallback Imports from sessions.py

**Current:**
```python
def _get_settings() -> "Settings":
    try:
        from ..dependencies import get_dependencies
        deps = get_dependencies()
        _settings_cache = deps.settings
        return _settings_cache
    except RuntimeError:
        from ..config.api_config import Settings
        _settings_cache = Settings()
    return _settings_cache
```

**New:**
```python
# Remove _get_settings() entirely
# Always require Settings to be passed explicitly

def get_async_engine(settings: Settings) -> AsyncEngine:
    """Create async engine - Settings is REQUIRED."""
    return sqlalchemy_create_async_engine(...)

def get_async_session(settings: Settings) -> AsyncSession:
    """Create async session - Settings is REQUIRED."""
    engine = get_async_engine(settings)
    ...
```

**Migration:**
- Update all call sites to pass `settings` explicitly
- Update `startup.py` to pass settings from dependencies

### Step 3: Remove Fallback Imports from Guardrails

**Current:**
```python
async def note_query_guardrail(...):
    try:
        from ...dependencies import get_dependencies
        deps = get_dependencies()
        settings = deps.settings
    except RuntimeError:
        from ...config.api_config import get_settings
        settings = get_settings()
    agent = get_note_query_guardrail_agent(settings=settings)
```

**New:**
```python
async def note_query_guardrail(
    ctx: RunContextWrapper[None],
    agent: Agent,
    input: str | list[TResponseInputItem],
    settings: Settings,  # Add explicit parameter
) -> GuardrailFunctionOutput:
    agent = get_note_query_guardrail_agent(settings=settings)
    ...
```

**Migration:**
- Update guardrail function signatures to accept `settings`
- Update call sites (agents) to pass settings
- Agents get settings from dependencies passed to them

### Step 4: Pass Dependencies Through Call Chain

**Current (global accessor):**
```python
# In guardrail
deps = get_dependencies()
settings = deps.settings

# In service
deps = get_dependencies()
client = deps.proxy_client_manager.get_client()
```

**New (explicit passing):**
```python
# In agent
class NoteQueryAgent:
    def __init__(self, dependencies: Dependencies):
        self.dependencies = dependencies
    
    async def run(self, ...):
        # Pass settings to guardrail
        result = await note_query_guardrail(
            ctx, agent, input,
            settings=self.dependencies.settings  # Explicit
        )

# In service
class NoteQueryService:
    def __init__(self, dependencies: Dependencies):
        self.dependencies = dependencies
    
    async def query(self, ...):
        # Use dependencies directly
        client = self.dependencies.proxy_client_manager.get_client()
```

### Step 5: FastAPI Dependency Injection

**Current:**
```python
@router.post("/query")
async def query(...):
    deps = get_dependencies()  # Global accessor
    service = NoteQueryService(dependencies=deps)
```

**New:**
```python
from fastapi import Depends

def get_dependencies() -> Dependencies:
    """FastAPI dependency - returns initialized dependencies."""
    # This is safe because dependencies are initialized at startup
    return _dependencies

@router.post("/query")
async def query(
    ...,
    deps: Dependencies = Depends(get_dependencies)
):
    service = NoteQueryService(dependencies=deps)
```

## Benefits

1. **No Circular Dependencies**: Clear dependency graph
2. **No Lazy Loading**: All dependencies initialized at startup
3. **No Fallback Logic**: Explicit is better than implicit
4. **Type Safety**: All dependencies are typed
5. **Testability**: Easy to inject test dependencies
6. **Maintainability**: Clear dependency flow

## Migration Order

1. ✅ **Step 1**: Eager initialization in `Dependencies.__init__`
2. ✅ **Step 2**: Remove fallbacks from `sessions.py`
3. ✅ **Step 3**: Update guardrails to accept `settings` parameter
4. ✅ **Step 4**: Update agents to pass settings to guardrails
5. ✅ **Step 5**: Update services to use explicit dependencies
6. ✅ **Step 6**: Update routers to use FastAPI DI
7. ✅ **Step 7**: Remove global `get_dependencies()` (keep for FastAPI DI only)

## Testing Strategy

1. **Unit Tests**: Create test `Dependencies` with test `Settings`
2. **Integration Tests**: Use real dependencies initialized at test setup
3. **No Monkey Patching**: All dependencies passed explicitly


# Utils Directory Cleanup Plan

## Purpose

This document outlines a comprehensive plan for cleaning up and organizing the `src/knowledge_agents/utils/` directory. It establishes principles, decision frameworks, and a step-by-step cleanup strategy.

## Current State Analysis

### Current Utils Directory Structure

**Location**: `src/knowledge_agents/utils/`

**Total Size**: ~3,800 lines across 16 modules

**Current Modules** (alphabetical):

1. **`agent_output_parser.py`** (~100 lines)
   - Parses agent RunResult into structured output
   - Handles file categorization and link generation
   - **Category**: Agent-specific utilities

2. **`agent_utils.py`** (~50 lines)
   - Single function: `extract_guardrail_name()`
   - **Category**: Agent-specific utilities

3. **`cache_utils.py`** (~275 lines)
   - Content hash-based caching
   - Cache metadata management
   - Cache validation and invalidation
   - **Category**: Infrastructure utilities

4. **`data_persistence.py`** (~430 lines)
   - File I/O for nodes/edges, sections/embeddings
   - Directory structure management
   - File processing orchestration
   - **Category**: Data management utilities

5. **`exception_handlers.py`** (~200 lines)
   - Exception handling classes and decorators
   - OpenAI, Guardrail, Service exception handlers
   - **Category**: Infrastructure utilities

6. **`file_logging.py`** (~200 lines)
   - Per-file logging context managers
   - stdout/stderr file handlers
   - **Category**: Infrastructure utilities

7. **`graph_utils.py`** (~650 lines)
   - Neo4j schema setup
   - Graph node/relationship creation
   - NotePlan file reading with metadata
   - Embedding storage in Neo4j
   - **Category**: Domain-specific utilities (Graph/Neo4j)

8. **`guardrail_metrics_util.py`** (~150 lines)
   - Guardrail metrics collection
   - **Category**: Domain-specific utilities (Guardrails)

9. **`guardrail_settings.py`** (~50 lines)
   - Settings retrieval for guardrails
   - **Category**: Configuration utilities

10. **`metadata_utils.py`** (~100 lines)
    - Response metadata generation
    - **Category**: API utilities

11. **`model_utils.py`** (~100 lines)
    - LiteLLM model configuration
    - **Category**: Model/LLM utilities

12. **`response_generator.py`** (~150 lines)
    - Response building from agent results
    - **Category**: API utilities

13. **`text_splitters.py`** (~360 lines)
    - Markdown/content splitting
    - Token-aware chunking
    - **Category**: Text processing utilities

14. **`usage_extraction.py`** (~50 lines)
    - Usage metrics extraction
    - **Category**: Metrics utilities

15. **`usage_patch.py`** (~50 lines)
    - Usage patching utilities
    - **Category**: Metrics utilities

16. **`vector_store_utils.py`** (~200 lines)
    - Text normalization
    - Token estimation
    - Embedding generation
    - **Category**: Vector store utilities

### Current Organization Patterns

**Well-Organized Examples:**
- ✅ `cache_utils.py` - Clear single responsibility (caching)
- ✅ `file_logging.py` - Focused on logging concerns
- ✅ `text_splitters.py` - Dedicated to text splitting
- ✅ `data_persistence.py` - Focused on file I/O and persistence

**Potential Issues:**
- ⚠️ `graph_utils.py` - Large (650 lines), multiple responsibilities
- ⚠️ `agent_output_parser.py` - Could be part of agent module
- ⚠️ `agent_utils.py` - Single function, might belong elsewhere
- ⚠️ `usage_extraction.py` + `usage_patch.py` - Could be combined
- ⚠️ `guardrail_metrics_util.py` + `guardrail_settings.py` - Related but separate

## Principles and Guidelines

### When to Keep in Utils

**Keep in `utils/` when:**

1. **General-purpose, reusable functions**
   - Used across multiple modules/domains
   - No strong coupling to specific domain logic
   - Examples: `cache_utils`, `file_logging`, `text_splitters`

2. **Infrastructure concerns**
   - Cross-cutting concerns (logging, caching, error handling)
   - Not tied to business logic
   - Examples: `exception_handlers`, `file_logging`

3. **Small, focused utilities**
   - Single responsibility
   - < 300 lines per module
   - Clear, well-defined purpose
   - Examples: `cache_utils`, `file_logging`

4. **Domain-agnostic utilities**
   - Could be used in any project
   - No knowledge of specific business entities
   - Examples: `text_splitters`, `cache_utils`

### When to Split Out into Separate Modules/Directories

**Split out when:**

1. **Domain-specific logic**
   - Tightly coupled to specific domain (e.g., Neo4j, Guardrails)
   - Belongs conceptually with domain code
   - Examples: `graph_utils.py` → `src/knowledge_agents/graph/` or `src/knowledge_agents/neo4j/`

2. **Large modules (> 500 lines)**
   - Multiple responsibilities
   - Could be split into smaller, focused modules
   - Examples: `graph_utils.py` (650 lines) could split into:
     - `graph_schema.py` - Schema setup
     - `graph_operations.py` - Node/relationship creation
     - `graph_embeddings.py` - Embedding storage

3. **Related functionality that should be grouped**
   - Multiple modules serving same domain
   - Better organized as a package
   - Examples: Guardrail utilities → `src/knowledge_agents/guardrails/`

4. **API-specific utilities**
   - Only used in API layer
   - Should live with API code
   - Examples: `response_generator.py`, `metadata_utils.py` → `src/knowledge_agents/api/`

5. **Agent-specific utilities**
   - Only used by agents
   - Should live with agent code
   - Examples: `agent_output_parser.py`, `agent_utils.py` → `src/knowledge_agents/agents/`

### Decision Framework

Use this decision tree:

```
Is it domain-specific?
├─ YES → Does it belong to a specific domain module?
│   ├─ YES → Move to domain module (e.g., agents/, graph/, api/)
│   └─ NO → Keep in utils/ but consider creating domain subdirectory
│
└─ NO → Is it infrastructure/cross-cutting?
    ├─ YES → Keep in utils/
    └─ NO → Is it general-purpose and reusable?
        ├─ YES → Keep in utils/
        └─ NO → Review: might belong elsewhere
```

### Size Guidelines

- **< 200 lines**: Single file in utils/ is fine
- **200-500 lines**: Consider if it should be split or moved
- **> 500 lines**: Should be split into smaller modules or moved to domain package

### Naming Conventions

- **`*_utils.py`**: General-purpose utilities (e.g., `cache_utils.py`)
- **`*_util.py`**: Single-purpose utility (e.g., `guardrail_metrics_util.py`)
- **`*_handlers.py`**: Exception/event handlers (e.g., `exception_handlers.py`)
- **`*_splitters.py`**: Text/content splitting (e.g., `text_splitters.py`)
- **Domain-specific**: Use domain name (e.g., `graph_utils.py` → consider `graph/` package)

## Cleanup Strategy

### Phase 1: Analysis and Categorization

**Goal**: Understand current state and categorize modules

**Tasks**:
1. ✅ Document all current modules (done above)
2. Analyze dependencies between modules
3. Identify circular dependencies
4. Map usage across codebase
5. Categorize each module:
   - **Keep in utils/** (general-purpose, infrastructure)
   - **Move to domain module** (domain-specific)
   - **Split into smaller modules** (too large)
   - **Combine with related modules** (too small, related)

### Phase 2: Low-Hanging Fruit

**Goal**: Quick wins with minimal risk

**Tasks**:
1. **Combine small related modules**:
   - `usage_extraction.py` + `usage_patch.py` → `usage_utils.py`
   - `guardrail_metrics_util.py` + `guardrail_settings.py` → `guardrail_utils.py`

2. **Move API-specific utilities**:
   - `response_generator.py` → `src/knowledge_agents/api/utils.py` or `src/knowledge_agents/api/response.py`
   - `metadata_utils.py` → `src/knowledge_agents/api/metadata.py`

3. **Move agent-specific utilities**:
   - `agent_output_parser.py` → `src/knowledge_agents/agents/parsing.py`
   - `agent_utils.py` → Merge into `src/knowledge_agents/agents/utils.py` or relevant agent module

### Phase 3: Domain-Specific Refactoring

**Goal**: Move domain-specific code to appropriate locations

**Tasks**:
1. **Graph/Neo4j utilities**:
   - Option A: Create `src/knowledge_agents/graph/` package
     - `graph/schema.py` - Schema setup
     - `graph/operations.py` - Node/relationship creation
     - `graph/embeddings.py` - Embedding storage
     - `graph/file_reading.py` - NotePlan file reading
   - Option B: Keep in utils but split:
     - `graph_schema.py`
     - `graph_operations.py`
     - `graph_embeddings.py`
   - **Recommendation**: Option A if graph operations grow, Option B if staying small

2. **Guardrail utilities**:
   - Create `src/knowledge_agents/guardrails/` package
     - `guardrails/metrics.py`
     - `guardrails/settings.py`
     - `guardrails/utils.py` (if needed)

3. **Vector store utilities**:
   - Keep in utils (general-purpose) OR
   - Create `src/knowledge_agents/vector/` if it grows
   - Current size (~200 lines) is fine in utils

### Phase 4: Infrastructure Consolidation

**Goal**: Organize infrastructure utilities

**Tasks**:
1. **Keep in utils/** (these are good):
   - `cache_utils.py` ✅
   - `file_logging.py` ✅
   - `text_splitters.py` ✅
   - `exception_handlers.py` ✅
   - `data_persistence.py` ✅

2. **Review for potential consolidation**:
   - `model_utils.py` - Consider if it belongs with model/LLM configuration
   - `vector_store_utils.py` - Consider if it belongs with vector store code

### Phase 5: Documentation and Standards

**Goal**: Establish patterns and document decisions

**Tasks**:
1. Update this document with final decisions
2. Create `utils/README.md` documenting organization principles
3. Add docstrings explaining why modules are in utils vs elsewhere
4. Update import patterns in `__init__.py`

## Specific Recommendations

### High Priority (Do First)

1. **Combine usage modules**:
   ```python
   # Before: usage_extraction.py + usage_patch.py
   # After: usage_utils.py
   ```

2. **Move API utilities**:
   ```python
   # Before: utils/response_generator.py, utils/metadata_utils.py
   # After: api/response.py, api/metadata.py
   ```

3. **Move agent utilities**:
   ```python
   # Before: utils/agent_output_parser.py, utils/agent_utils.py
   # After: agents/parsing.py, agents/utils.py
   ```

### Medium Priority (Do Next)

4. **Split graph_utils.py**:
   ```python
   # Option A: Create graph/ package
   graph/
     __init__.py
     schema.py
     operations.py
     embeddings.py
     file_reading.py
   
   # Option B: Split in utils/
   utils/
     graph_schema.py
     graph_operations.py
     graph_embeddings.py
     graph_file_reading.py
   ```

5. **Consolidate guardrail utilities**:
   ```python
   # Before: guardrail_metrics_util.py + guardrail_settings.py
   # After: guardrails/metrics.py + guardrails/settings.py
   ```

### Low Priority (Future Consideration)

6. **Review model_utils.py**:
   - If model configuration grows, consider `models/` package
   - Currently fine in utils

7. **Review vector_store_utils.py**:
   - If vector operations grow, consider `vector/` package
   - Currently fine in utils

## Examples and Patterns

### Good Examples (Keep in Utils)

**`cache_utils.py`** ✅
- **Why**: General-purpose, reusable across domains
- **Size**: ~275 lines (good size)
- **Dependencies**: Minimal (hashlib, json, pathlib)
- **Usage**: Used by data_persistence, potentially others

**`file_logging.py`** ✅
- **Why**: Infrastructure concern, cross-cutting
- **Size**: ~200 lines (good size)
- **Dependencies**: Standard library only
- **Usage**: Used by data_persistence

**`text_splitters.py`** ✅
- **Why**: General-purpose text processing
- **Size**: ~360 lines (acceptable)
- **Dependencies**: LangChain (external), vector_store_utils
- **Usage**: Used by data_persistence, potentially others

### Examples Needing Refactoring

**`graph_utils.py`** ⚠️
- **Why**: Domain-specific (Neo4j), large (650 lines)
- **Recommendation**: Split into `graph/` package or split in utils
- **Dependencies**: Neo4j driver, domain types
- **Usage**: Used by notebooks, scripts, potentially API

**`agent_output_parser.py`** ⚠️
- **Why**: Agent-specific, only used by agents
- **Recommendation**: Move to `agents/parsing.py`
- **Dependencies**: Agent types, notes package
- **Usage**: Only used by agent code

**`response_generator.py`** ⚠️
- **Why**: API-specific, only used by API layer
- **Recommendation**: Move to `api/response.py`
- **Dependencies**: Agent types, API types
- **Usage**: Only used by API endpoints

## Migration Checklist

When moving a module:

- [ ] Update all imports across codebase
- [ ] Update `__init__.py` exports
- [ ] Update documentation references
- [ ] Run tests to ensure nothing breaks
- [ ] Update notebook imports if applicable
- [ ] Update script imports if applicable
- [ ] Add deprecation notice if needed (for gradual migration)
- [ ] Update this document with final location

## Success Criteria

**Cleanup is successful when:**

1. ✅ All modules have clear, single responsibilities
2. ✅ Domain-specific code lives in domain modules
3. ✅ Utils contains only general-purpose/infrastructure utilities
4. ✅ No modules exceed 500 lines (unless well-justified)
5. ✅ Related functionality is grouped together
6. ✅ Import paths are logical and intuitive
7. ✅ Documentation explains organization decisions
8. ✅ No circular dependencies introduced

## Notes and Considerations

### Backward Compatibility

- Consider deprecation warnings for moved modules
- Use `__init__.py` re-exports during transition period
- Document migration path for users

### Testing

- Ensure all tests pass after each move
- Update test imports
- Consider integration tests for moved modules

### Documentation

- Update docstrings with new locations
- Update README files
- Update architecture diagrams if they exist

### Performance

- Moving modules shouldn't affect performance
- But verify import times don't increase significantly

## Future Considerations

### Potential New Organization Patterns

1. **Domain Packages**:
   ```
   src/knowledge_agents/
     agents/
       utils.py
       parsing.py
     graph/
       schema.py
       operations.py
     api/
       response.py
       metadata.py
     guardrails/
       metrics.py
       settings.py
   ```

2. **Infrastructure Package**:
   ```
   src/knowledge_agents/
     infrastructure/
       caching.py
       logging.py
       exceptions.py
   ```

3. **Keep Utils Simple**:
   ```
   src/knowledge_agents/
     utils/
       text_splitters.py
       data_persistence.py
       vector_store_utils.py
   ```

**Recommendation**: Start with Option 3 (keep utils simple), move domain-specific code out. Only create infrastructure package if it grows significantly.

## Execution Plan

### Step 1: Review and Approve
- Review this plan
- Get consensus on principles
- Prioritize cleanup tasks

### Step 2: Execute Phase 2 (Low-Hanging Fruit)
- Combine small modules
- Move API/agent utilities
- Test thoroughly

### Step 3: Execute Phase 3 (Domain Refactoring)
- Split large modules
- Move domain-specific code
- Test thoroughly

### Step 4: Document and Standardize
- Update documentation
- Establish patterns
- Create guidelines

### Step 5: Review and Iterate
- Review results
- Adjust as needed
- Document lessons learned

---

**Last Updated**: 2025-11-23
**Status**: Planning Phase
**Next Review**: After Phase 2 completion


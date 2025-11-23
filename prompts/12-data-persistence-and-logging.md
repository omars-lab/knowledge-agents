# Data Persistence and Logging Mechanisms

## Purpose

This document defines the data persistence and logging mechanisms used throughout the knowledge-agents project. It provides guidelines for maintaining consistency and ensuring all file processing follows the established patterns.

## Core Principles

1. **Automatic File Logging**: All processing logs are automatically written to per-file stdout.log and stderr.log files
2. **Structured Data Storage**: Each NotePlan file generates 4 output files in a mirrored directory structure
3. **Caching Mechanism**: Processed files are cached to avoid redundant processing
4. **Seamless Integration**: Logging happens automatically without manual capture or redirection
5. **Dual Output**: Logs appear in both console (for real-time feedback) and files (for persistence)

## File Structure

### Data Directory Layout

All processed data is stored in `build/data/` with a structure that mirrors the NotePlan folder hierarchy:

```
build/data/
├── Calendar/
│   ├── 2025-01-15_nodes_edges.json
│   ├── 2025-01-15_sections_embeddings.json
│   ├── 2025-01-15_stdout.log
│   └── 2025-01-15_stderr.log
├── Notes/
│   └── project-ideas/
│       ├── project-ideas_nodes_edges.json
│       ├── project-ideas_sections_embeddings.json
│       ├── project-ideas_stdout.log
│       └── project-ideas_stderr.log
└── np-out.log/
    ├── np-out_nodes_edges.json
    ├── np-out_sections_embeddings.json
    ├── np-out_stdout.log
    └── np-out_stderr.log
```

### File Types Per NotePlan File

Each NotePlan file that is processed generates exactly 4 files:

1. **`{filename}_nodes_edges.json`**: Extracted entities and relationships
   - Contains: `entities`, `relationships`, `insights`, `file_path`
   - Format: JSON with structured data from graph builder agent

2. **`{filename}_sections_embeddings.json`**: Sections with embeddings and tokens
   - Contains: `sections` array, `total_sections`, `file_path`
   - Each section has: `content`, `embedding` (list of floats), `tokens` (int), `section_index`

3. **`{filename}_stdout.log`**: Standard output log
   - Contains: INFO level and above log messages
   - Includes: Processing progress, extraction results, embedding generation status
   - Format: Timestamped log entries with logger name and line numbers

4. **`{filename}_stderr.log`**: Standard error log
   - Contains: WARNING level and above log messages
   - Includes: Errors, warnings, exceptions
   - Format: Timestamped log entries with logger name and line numbers

## Logging Mechanism

### File Logging Context

The `file_logging_context` context manager automatically sets up logging for each file:

```python
from knowledge_agents.utils import file_logging_context, setup_file_logger

# Set up log file paths
stdout_file, stderr_file = setup_file_logger(relative_path, data_dir)

# Use context manager - all logging is automatic
with file_logging_context(stdout_file, stderr_file):
    logger.info("This goes to stdout.log AND console")
    logger.error("This goes to stderr.log AND console")
    print("This also goes to stdout.log AND console")
```

### Key Features

- **Automatic Capture**: All logger calls and print statements are captured
- **Dual Output**: Logs appear in both console and files simultaneously
- **Proper Formatting**: Timestamps, log levels, logger names, and line numbers
- **Clean Separation**: INFO+ to stdout.log, WARNING+ to stderr.log
- **Exception Handling**: Logs are saved even if processing fails

### Logging Best Practices

1. **Use logger, not print**: Prefer `logger.info()` over `print()` for better control
2. **Include context**: Always include file path or relevant context in log messages
3. **Use appropriate levels**:
   - `logger.debug()`: Detailed diagnostic information
   - `logger.info()`: General informational messages
   - `logger.warning()`: Warning messages (goes to stderr.log)
   - `logger.error()`: Error messages (goes to stderr.log)
4. **Include exceptions**: Use `exc_info=True` when logging exceptions

## Data Persistence Functions

### Core Functions

Located in `src/knowledge_agents/utils/data_persistence.py`:

1. **`get_data_dir(base_dir, noteplan_dir)`**: Creates `build/data/` directory
2. **`get_file_data_dir(data_dir, relative_path)`**: Creates directory structure mirroring NotePlan
3. **`get_file_base_name(relative_path)`**: Extracts base filename without extension
4. **`save_nodes_edges(data_dir, relative_path, output)`**: Saves entities/relationships to JSON
5. **`save_sections_embeddings(data_dir, relative_path, sections)`**: Saves sections with embeddings
6. **`check_file_cached(data_dir, relative_path, ...)`**: Simple check if data files exist
7. **`load_nodes_edges(file_path)`**: Loads cached nodes/edges JSON
8. **`load_sections_embeddings(file_path)`**: Loads cached sections/embeddings JSON

### Cache Utilities

Located in `src/knowledge_agents/utils/cache_utils.py`:

1. **`compute_content_hash(file_path)`**: Computes SHA256 hash of file content
2. **`check_file_cache_valid(cache_file_path, ...)`**: Validates cache with content hash checking
3. **`check_data_file_cache(...)`**: Enhanced cache check for NotePlan files with metadata
4. **`save_cache_metadata(cache_file_path, ...)`**: Saves cache metadata (computes content hash)
5. **`invalidate_cache(cache_file_path)`**: Deletes cache file and metadata
6. **`CacheMetadata`**: Dataclass for cache metadata (includes content hash)

**When to use which**:
- **`check_file_cached()`**: Simple existence check (fast, no metadata)
- **`check_data_file_cache()`**: When you need content hash validation or metadata

### Main Processing Function

**`process_file_with_sections_and_embeddings()`**:

```python
async def process_file_with_sections_and_embeddings(
    file_path: Path,
    relative_path: str,
    dependencies: Dependencies,
    data_dir: Path,
    generate_embeddings_flag: bool = True,
    use_cache: bool = True,
) -> Tuple[Optional[GraphBuilderAgentOutput], List[Dict[str, Any]]]:
```

**What it does:**
1. Sets up file logging automatically
2. Reads NotePlan file content
3. Extracts entities/relationships using graph builder agent
4. Splits content into sections
5. Generates embeddings for sections (if requested)
6. Returns extracted data (logs are automatically saved)

**Returns:**
- `output`: GraphBuilderAgentOutput with entities/relationships (or None if failed)
- `sections_with_embeddings`: List of section dicts with embeddings and tokens

**Note:** Logs are automatically written to stdout.log and stderr.log - no need to capture or return them.

## Caching Mechanism

### Core Difference: Content Hash vs File Existence

**The fundamental difference** between the two caching approaches:

- **Simple (`check_file_cached`)**: "Does the cache file exist?" → Fast, but no validation
- **Enhanced (`check_data_file_cache`)**: "Does the cache file exist AND does the source file content match?" → Validates using SHA256 content hash

**Why Content Hash?**
- More reliable than modification time (mtime can change without content changing)
- Detects actual content changes (same content = same hash)
- Automatic invalidation when source file content changes
- Works even if file is copied/moved (hash follows content, not metadata)

### Two Caching Approaches

We have two caching utilities for different use cases:

#### 1. Simple File Existence Check (`check_file_cached`)

**Use when**: You just need to know if cache files exist (fast, simple)

```python
from knowledge_agents.utils import check_file_cached, load_nodes_edges

# Simple check - just verifies files exist
is_cached, nodes_edges_path, _ = check_file_cached(
    data_dir, relative_path, 
    check_nodes_edges=True, 
    check_sections_embeddings=False
)
```

**Pros**: Fast, simple, no metadata overhead
**Cons**: No modification time checking, no cache metadata

#### 2. Enhanced Cache Validation (`check_data_file_cache`)

**Use when**: You need content hash validation or cache metadata

```python
from knowledge_agents.utils import check_data_file_cache, load_nodes_edges

# Enhanced check - validates content hashes
is_cached, nodes_edges_path, _, metadata = check_data_file_cache(
    data_dir, relative_path,
    check_nodes_edges=True,
    source_file_path=file_path,  # For content hash checking
    check_content_hash=True,  # Invalidate if source file content changed
)

if is_cached and metadata:
    print(f"Cached at: {metadata.cached_at}")
    print(f"Source content hash: {metadata.source_content_hash[:16]}...")
```

**Pros**: Content hash validation (more reliable than modification time), cache metadata, automatic invalidation
**Cons**: Slightly slower (computes SHA256 hash of source file)

### How Caching Works

1. **Check Before Processing**: Before processing a file, check if cache files exist
2. **Skip if Cached**: If cached file exists and is valid, skip processing and load from cache
3. **Cache Key**: Based on relative path from NotePlan root
4. **Cache Location**: Same directory structure as output files
5. **Cache Metadata**: Optional metadata files store when cache was created and source file info

### Cache Metadata

Cache metadata files (`{filename}_metadata.json`) store:
- `cached_at`: When the cache was created
- `source_file_path`: Path to the source NotePlan file
- `source_content_hash`: SHA256 hash of source file content when cached (for validation)
- `cache_version`: Version of cache format
- `additional_metadata`: Any extra metadata

**Content Hash Validation**: Cache staleness is determined by comparing the current source file's content hash with the cached hash. If hashes differ, the cache is invalid (content changed). This is more reliable than modification time checking because:
- File content can change without modification time updating (e.g., file copied)
- Modification time can change without content changing (e.g., permissions, metadata)
- Content hash guarantees: same content = same hash, different content = different hash

### Caching Best Practices

1. **Choose the right function**:
   - Use `check_file_cached()` for simple existence checks
   - Use `check_data_file_cache()` when you need modification time validation
2. **Check cache first**: Always check cache before processing
3. **Respect cache flag**: Use `use_cache` parameter to control caching behavior
4. **Cache invalidation**: 
   - Simple: Delete cached JSON files or set `use_cache=False`
   - Enhanced: Use `invalidate_cache()` or rely on modification time checking
5. **Partial cache**: Can check for nodes_edges.json and/or sections_embeddings.json independently

### Example Usage

**Simple caching (current default)**:
```python
from knowledge_agents.utils import check_file_cached, load_nodes_edges

# Check if cached
is_cached, nodes_edges_path, _ = check_file_cached(
    data_dir, relative_path, 
    check_nodes_edges=True, 
    check_sections_embeddings=False
)

if is_cached and nodes_edges_path:
    # Load from cache
    cached_data = load_nodes_edges(nodes_edges_path)
    print(f"Cached: {len(cached_data['entities'])} entities")
else:
    # Process file
    output, sections = await process_file_with_sections_and_embeddings(...)
```

**Enhanced caching with content hash validation**:
```python
from knowledge_agents.utils import check_data_file_cache, load_nodes_edges

# Check cache with content hash validation
is_cached, nodes_edges_path, _, metadata = check_data_file_cache(
    data_dir, relative_path,
    check_nodes_edges=True,
    source_file_path=file_path,
    check_content_hash=True,  # Auto-invalidate if source content changed
)

if is_cached and nodes_edges_path:
    cached_data = load_nodes_edges(nodes_edges_path)
    print(f"Cached at: {metadata.cached_at}")
    print(f"Source hash: {metadata.source_content_hash[:16]}...")
    print(f"Entities: {len(cached_data['entities'])}")
else:
    # Process file (cache invalid or doesn't exist)
    output, sections = await process_file_with_sections_and_embeddings(...)
    # Save with source_file_path to compute and store content hash
    if output:
        save_nodes_edges(data_dir, relative_path, output, source_file_path=file_path)
```

## Processing Workflow

### Standard Processing Pattern

```python
from knowledge_agents.utils import (
    check_file_cached,
    get_data_dir,
    load_nodes_edges,
    process_file_with_sections_and_embeddings,
    save_nodes_edges,
    save_sections_embeddings,
)

# Set up data directory
data_dir = get_data_dir(project_root / "build", NOTEPLAN_DIR)

# Process each file
for file_path, mod_time in files:
    relative_path = str(file_path.relative_to(NOTEPLAN_DIR))
    
    # Check cache
    is_cached, _, _ = check_file_cached(data_dir, relative_path, ...)
    if is_cached:
        # Load from cache
        continue
    
    # Process file (logging is automatic)
    output, sections = await process_file_with_sections_and_embeddings(
        file_path=file_path,
        relative_path=relative_path,
        dependencies=dependencies,
        data_dir=data_dir,
        generate_embeddings_flag=True,
        use_cache=False,  # Already checked above
    )
    
    # Save results
    if output:
        save_nodes_edges(data_dir, relative_path, output)
    if sections:
        save_sections_embeddings(data_dir, relative_path, sections)
    
    # Note: stdout.log and stderr.log are automatically created
```

## Critical Rules - DO NOT DEVIATE

### ❌ NEVER:

1. **Don't manually capture stdout/stderr**: Use `file_logging_context` instead of StringIO or redirect
2. **Don't skip file logging**: Always use `file_logging_context` when processing files
3. **Don't change file structure**: Keep the 4-file-per-NotePlan-file structure
4. **Don't bypass caching**: Always check cache before processing
5. **Don't hardcode paths**: Use `get_data_dir()` and `get_file_data_dir()` utilities
6. **Don't mix logging approaches**: Use logger, not print (or use file_logging_context if print is needed)
7. **Don't use modification time for cache validation**: Always use content hash (`check_content_hash=True`)
8. **Don't forget source_file_path**: Always pass `source_file_path` to `save_nodes_edges()` and `save_sections_embeddings()` for hash computation

### ✅ ALWAYS:

1. **Use file_logging_context**: Wrap file processing in `file_logging_context()`
2. **Check cache first**: Always check `check_file_cached()` or `check_data_file_cache()` before processing
3. **Save all 4 files**: Ensure nodes_edges.json, sections_embeddings.json, stdout.log, stderr.log are created
4. **Mirror directory structure**: Use `get_file_data_dir()` to maintain NotePlan folder structure
5. **Use proper logging levels**: INFO+ to stdout, WARNING+ to stderr
6. **Include context in logs**: Always include file path or relevant context
7. **Use content hash for cache validation**: Pass `source_file_path` to save functions and use `check_content_hash=True`
8. **Compute content hash when saving**: Always pass `source_file_path` to `save_nodes_edges()` and `save_sections_embeddings()`

## Integration Points

### Notebooks

- **`02o1-extracting-data.ipynb`**: Uses data persistence and file logging
- **`02-extracting-embeddings.ipynb`**: May use sections/embeddings loading
- **`03-loading-data.ipynb`**: May load cached nodes/edges

### Scripts

- **`scripts/seed_graph_database.py`**: May use data persistence utilities
- **`scripts/seed_neo4j_vector_store.py`**: May use sections/embeddings loading

### Utilities

- **`src/knowledge_agents/utils/data_persistence.py`**: Core data persistence functions
- **`src/knowledge_agents/utils/file_logging.py`**: File logging context manager
- **`src/knowledge_agents/utils/graph_utils.py`**: Graph extraction utilities (uses logging)

## Review Checklist

When reviewing code that processes NotePlan files, verify:

- [ ] Uses `file_logging_context` for automatic logging
- [ ] Checks cache before processing
- [ ] Saves all 4 required files (nodes_edges, sections_embeddings, stdout, stderr)
- [ ] Uses `get_data_dir()` and `get_file_data_dir()` for paths
- [ ] Maintains directory structure mirroring NotePlan
- [ ] Uses appropriate logging levels (INFO vs WARNING/ERROR)
- [ ] Includes file path context in log messages
- [ ] Handles exceptions gracefully (logs are still saved)

## Future Enhancements

Potential improvements (documented for future consideration):

1. **Section splitting**: Enhance `split_content_into_sections()` to split by headings or chunks
2. **Cache validation**: Add timestamp/modification time checking for cache invalidation
3. **Incremental processing**: Only process changed files based on modification time
4. **Compression**: Consider compressing large JSON files
5. **Index file**: Create an index.json mapping NotePlan files to their data files
6. **Batch operations**: Optimize for processing multiple files in parallel

## Examples

### Complete Example: Processing a File

```python
import asyncio
from pathlib import Path
from knowledge_agents.utils import (
    get_data_dir,
    check_file_cached,
    process_file_with_sections_and_embeddings,
    save_nodes_edges,
    save_sections_embeddings,
)
from knowledge_agents.dependencies import Dependencies

# Setup
NOTEPLAN_DIR = Path("/path/to/noteplan")
project_root = Path("/path/to/project")
data_dir = get_data_dir(project_root / "build", NOTEPLAN_DIR)
dependencies = Dependencies(settings=settings)

# Process file
file_path = NOTEPLAN_DIR / "Calendar/2025-01-15.md"
relative_path = "Calendar/2025-01-15.md"

# Check cache
is_cached, _, _ = check_file_cached(data_dir, relative_path)
if is_cached:
    print("File already processed, skipping")
    return

# Process (logging is automatic)
output, sections = await process_file_with_sections_and_embeddings(
    file_path=file_path,
    relative_path=relative_path,
    dependencies=dependencies,
    data_dir=data_dir,
    generate_embeddings_flag=True,
)

# Save results
if output:
    save_nodes_edges(data_dir, relative_path, output)
if sections:
    save_sections_embeddings(data_dir, relative_path, sections)

# Files created:
# - build/data/Calendar/2025-01-15_nodes_edges.json
# - build/data/Calendar/2025-01-15_sections_embeddings.json
# - build/data/Calendar/2025-01-15_stdout.log
# - build/data/Calendar/2025-01-15_stderr.log
```

## References

- **Implementation**: `src/knowledge_agents/utils/data_persistence.py`
- **Logging**: `src/knowledge_agents/utils/file_logging.py`
- **Usage Example**: `notebooks/02o1-extracting-data.ipynb`
- **Graph Utils**: `src/knowledge_agents/utils/graph_utils.py`


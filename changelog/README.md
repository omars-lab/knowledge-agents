# Changelog Entries

This directory contains individual changelog entries, each mapped to a specific git commit.

## Entry Format

Each entry file uses YAML front matter for metadata, followed by markdown content:

```yaml
---
commit: <git-commit-hash>
date: YYYY-MM-DD
type: Added|Changed|Fixed|Deprecated|Removed|Security
---

# Title

## Description
Brief overview

## Changes
- Detailed list of changes

## Impact
Effect of the changes
```

The front matter contains:
- **commit**: Git commit hash
- **date**: Commit date (YYYY-MM-DD format)
- **type**: Entry type (Added, Changed, Fixed, etc.)

## Entries

### [Unreleased] - Commit `c6a50ea` (2025-11-14)

#### Added
- [001-agent-file-organization-refactoring.md](001-agent-file-organization-refactoring.md) - Agent file organization refactoring
- [002-usage-reporting.md](002-usage-reporting.md) - Usage reporting
- [003-response-metadata-headers.md](003-response-metadata-headers.md) - Response metadata headers
- [004-mcp-integration.md](004-mcp-integration.md) - MCP integration
- [005-api-key-management.md](005-api-key-management.md) - API key management
- [006-framework-compatibility.md](006-framework-compatibility.md) - Framework compatibility
- [015-neo4j-graph-infrastructure.md](015-neo4j-graph-infrastructure.md) - Neo4j graph infrastructure

#### Changed
- [007-agent-architecture-refactor.md](007-agent-architecture-refactor.md) - Agent architecture refactor
- [008-mcp-tool-integration.md](008-mcp-tool-integration.md) - MCP tool integration
- [009-api-key-loading.md](009-api-key-loading.md) - API key loading
- [010-error-handling.md](010-error-handling.md) - Error handling

#### Fixed
- [011-import-error-fix.md](011-import-error-fix.md) - Import error fix
- [012-usage-extraction-fix.md](012-usage-extraction-fix.md) - Usage extraction fix

### Previous Releases - Commit `a945fde` (2025-11-03)

#### Added
- [013-note-query-system-implementation.md](013-note-query-system-implementation.md) - Note query system implementation
- [014-infrastructure.md](014-infrastructure.md) - Infrastructure

## How to Add New Entries

1. Create a new file with format: `XXX-description.md` (where XXX is the next sequential number)
2. Add YAML front matter with `commit`, `date`, and `type` fields
3. Include description, changes, and impact sections in markdown
4. Update this README.md to include the new entry
5. Update the main CHANGELOG.md to reference the entry


# Notebook Structure, Philosophy, and Review Guidelines

## Purpose

This document defines the structure, philosophy, and approach for organizing Jupyter notebooks in the knowledge-agents project. It provides guidelines for reviewing existing notebooks to detect deviations and maintain consistency.

## Notebook Structure Philosophy

### Core Principles

1. **Progressive Complexity**: Notebooks should follow a logical progression from setup → extraction → loading → querying
2. **Option-Based Alternatives**: When multiple approaches exist for the same task, use option numbering (e.g., `02o1`, `02o2`)
3. **Centralized Setup**: Common imports, configuration, and setup should be centralized in `00-import.ipynb`
4. **Clear Prerequisites**: Each notebook should clearly document what must be completed before running it
5. **Layman-Friendly Overviews**: Overview sections should start with simple, high-level purpose statements
6. **Clickable Navigation**: All notebook references should use markdown links for easy navigation

### Naming Convention

- **Sequential notebooks**: `00-import.ipynb`, `01-setup-database.ipynb`, `02-extracting-data.ipynb`, etc.
- **Option notebooks**: `02o1-extracting-data.ipynb` (option 1), `02o2-extracting-data-langchain.ipynb` (option 2)
- **Descriptive suffixes**: Include the technology/method in the filename (e.g., `-neo4j`, `-langchain`, `-qdrant`)

### Standard Notebook Structure

Each notebook should follow this structure:

```markdown
# XX: Notebook Title

Brief description of what this notebook does.

## Prerequisites

**⚠️ Important:** Before running this notebook, ensure you have:
- Completed [**00-import.ipynb**](./00-import.ipynb) for environment detection and Neo4j connection setup
- Completed [**XX-previous-notebook.ipynb**](./XX-previous-notebook.ipynb) for [specific requirement]

All environment detection, Neo4j connection, and configuration are handled in `00-import.ipynb`.

## Overview

[Simple, layman-friendly explanation of what this notebook does and why it's useful]

**Alternative Approach:** [If applicable] If you prefer [alternative method], see [**XXoY-alternative.ipynb**](./XXoY-alternative.ipynb) for an alternative approach.

We'll:
1. [Step 1]
2. [Step 2]
3. [Step 3]

## [Section 1 Title]

[Description]

## [Section 2 Title]

[Description]

## Next Steps

Now that [current task] is complete, proceed to:
- [**XX-next-notebook.ipynb**](./XX-next-notebook.ipynb): [Description]
```

## Required Sections

### 1. Prerequisites Section
- **Must include**: Reference to `00-import.ipynb`
- **Must include**: Any specific notebooks that must be run first
- **Must include**: Statement that environment detection/configuration is handled in `00-import.ipynb`
- **Should not include**: Steps that are already done in `00-import.ipynb` (e.g., "Detect environment", "Connect to Neo4j")

### 2. Overview Section
- **Must start with**: A simple, high-level purpose statement in layman terms
- **Must include**: "We'll:" list of steps
- **Should include**: Alternative approach references if applicable
- **Should not include**: Technical implementation details (save for later sections)

### 3. Setup/Import Section
- **Must include**: `%run 00-import.ipynb` as the first command
- **Should include**: Additional imports specific to this notebook
- **Should not duplicate**: Imports already done in `00-import.ipynb`

### 4. Next Steps Section
- **Must include**: Clickable links to next notebooks
- **Should include**: Brief description of what each next notebook does
- **Should reference**: The correct notebook names (including option numbers if applicable)

## Option Notebooks Pattern

When multiple approaches exist for the same task:

1. **Primary notebook** gets option number `o1` (e.g., `02o1-extracting-data.ipynb`)
2. **Alternative notebooks** get subsequent option numbers (e.g., `02o2-extracting-data-langchain.ipynb`)
3. **Cross-references**: Each option notebook should reference the others in the Overview section
4. **Comparison section**: Option notebooks should include a comparison section explaining differences

### Example Pattern

```
02o1-extracting-data.ipynb (Agent-based extraction)
  ├─ Overview mentions: "Alternative: 02o2-extracting-data-langchain.ipynb"
  └─ Next Steps: Points to 03-loading-data.ipynb

02o2-extracting-data-langchain.ipynb (LangChain extraction)
  ├─ Overview mentions: "Alternative to 02o1-extracting-data.ipynb"
  ├─ Comparison section: Explains differences
  └─ Next Steps: Points to 03-loading-data.ipynb
```

## Common Patterns to Check

### ✅ Good Patterns

1. **Centralized Setup**: All notebooks use `%run 00-import.ipynb`
2. **No Duplication**: No duplicate environment detection or connection setup code
3. **Clear Prerequisites**: Prerequisites section clearly lists required notebooks
4. **Clickable Links**: All notebook references use markdown link syntax `[**name**](./path)`
5. **Layman Overviews**: Overview sections start with simple explanations
6. **Consistent Naming**: Option notebooks follow `XXoY-description` pattern

### ❌ Anti-Patterns to Detect

1. **Duplicate Setup Code**: Notebooks that re-implement environment detection or connection setup
2. **Missing Prerequisites**: Notebooks that don't clearly state what must be run first
3. **Plain Text References**: Notebook references that aren't clickable links
4. **Technical Overviews**: Overview sections that jump straight into technical details
5. **Inconsistent Naming**: Option notebooks that don't follow the `XXoY` pattern
6. **Missing Alternatives**: Primary notebooks that don't mention alternative approaches
7. **Broken Links**: References to notebooks that don't exist or have been renamed
8. **Outdated References**: References to old notebook names after renaming

## Review Checklist

When reviewing notebooks, check:

- [ ] **Structure**: Does it follow the standard structure (Prerequisites → Overview → Sections → Next Steps)?
- [ ] **Prerequisites**: Are all required notebooks listed with clickable links?
- [ ] **Overview**: Does it start with a layman-friendly purpose statement?
- [ ] **Alternatives**: Are alternative approaches mentioned if they exist?
- [ ] **Setup**: Does it use `%run 00-import.ipynb` and avoid duplicating setup code?
- [ ] **Naming**: Does it follow the naming convention (sequential or option-based)?
- [ ] **Links**: Are all notebook references clickable markdown links?
- [ ] **Next Steps**: Do Next Steps reference the correct notebook names?
- [ ] **Consistency**: Are option notebooks properly cross-referenced?

## Healing Process

When detecting deviations:

1. **Identify the deviation**: What pattern is being violated?
2. **Check related notebooks**: Are other notebooks also affected?
3. **Update systematically**: Fix all instances, not just one
4. **Verify links**: Ensure all cross-references are updated
5. **Test structure**: Verify the notebook still follows the standard structure
6. **Update this document**: If a new pattern emerges, document it here

## Current Notebook Structure

### Sequential Notebooks
- `00-import.ipynb`: Common imports and setup
- `01-setup-database.ipynb`: Neo4j database setup and vector index creation
- `02-extracting-embeddings.ipynb`: Generate vector embeddings from NotePlan notes (not an option - standalone)
- `03-loading-data.ipynb`: Load entities and relationships into Neo4j
- `05-querying-graph.ipynb`: Query Neo4j graph with Cypher
- `06-querying-vector-embeddings.ipynb`: Query vector embeddings (assumes Neo4j)

### Option Notebooks

#### Entity/Relationship Extraction Options
- `02o1-extracting-data.ipynb`: Agent-based extraction (primary)
- `02o2-extracting-data-langchain.ipynb`: LangChain-based extraction (alternative)

**Note:** These extract entities/relationships, which is different from `02-extracting-embeddings.ipynb` which extracts vector embeddings.

#### Vector Embedding Storage Options
- `04o1-loading-vector-embeddings-neo4j.ipynb`: Store embeddings in Neo4j (primary)
- `04o2-loading-vector-embeddings-qdrant.ipynb`: Store embeddings in Qdrant (alternative) [TODO: Create - currently referenced but not implemented]

**Note:** These notebooks require embeddings to be generated in `02-extracting-embeddings.ipynb` first. They do not generate embeddings themselves - they only store pre-generated embeddings.

## Future Considerations

- **Querying Options**: May need `06o1-querying-vector-embeddings-neo4j.ipynb` and `06o2-querying-vector-embeddings-qdrant.ipynb` if querying differs
- **Visualization Options**: May need option notebooks for different visualization approaches
- **Personalization Options**: May need option notebooks for different personalization strategies

## Review Command

To review notebooks for deviations, use:

```bash
# Check for broken links
grep -r "\.ipynb" notebooks/ | grep -v "\.ipynb" | grep -v "^#"

# Check for non-clickable references
grep -r "\*\*.*\.ipynb\*\*" notebooks/ | grep -v "\["

# Check for missing prerequisites sections
# (manual review needed)
```

## Notes

- This document should be updated as new patterns emerge
- When adding new notebooks, ensure they follow these guidelines
- When renaming notebooks, update all cross-references
- Option notebooks should be created when multiple valid approaches exist for the same task


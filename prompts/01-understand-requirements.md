# Requirements Analysis Process

## Step 1: Initial Requirements Scan
Read through the `docs/00-requirements.txt` file and identify:
- Project title and context
- Main deliverables expected
- Time constraints
- Technology constraints

## Step 2: Core Functionality Extraction
Look for the primary technical requirements:
- What is the main API endpoint supposed to do?
- What inputs does it accept?
- What outputs should it produce?
- What external services/integrations are required?

## Step 3: Business Logic Requirements
Identify all validation and business rules:
- What conditions should trigger error responses?
- What data should be filtered or excluded?
- What user inputs need validation?

## Step 4: Data Model Analysis
Extract information about:
- Required data structures
- Sample data provided
- Relationships between entities
- Data storage requirements

## Step 5: Technical Constraints
Note all technical limitations:
- Allowed programming languages
- Framework restrictions
- Database requirements
- Performance expectations

## Step 6: Deliverables Breakdown
List all required outputs:
- Code deliverables
- Testing requirements
- Documentation needs
- Demo requirements

## Step 7: Success Criteria Definition
Identify how success will be measured:
- Functional requirements
- Performance requirements
- Quality requirements
- Acceptance criteria

## Step 7.5: Ambiguity Analysis
Identify ambiguous or unclear requirements and formulate clarifying questions:

### Ambiguous Requirements to Flag
- Requirements that could be interpreted multiple ways
- Missing technical specifications
- Unclear business logic
- Vague acceptance criteria
- Missing edge cases

### Clarifying Questions to Ask
For each ambiguous requirement, formulate specific questions such as:
- "What should happen when [specific scenario]?"
- "How should the system handle [edge case]?"
- "What is the expected format for [output/input]?"
- "What are the performance requirements for [specific function]?"
- "How should [error condition] be handled?"

### Document Ambiguities
Create a section in your analysis for:
- **Ambiguous Requirements**: List unclear requirements with your interpretation
- **Clarifying Questions**: Specific questions to resolve ambiguities
- **Assumptions Made**: Document assumptions you'll make if clarification isn't available

## Step 8: Extract Key Requirements
Based on the analysis above, extract the most critical requirements and save them to `docs/01-key-requirements.txt` with the following format:

```
# Key Requirements

## Core Functionality
- [Requirement 1]
- [Requirement 2]

## Business Logic
- [Requirement 1]
- [Requirement 2]

## Technical Constraints
- [Requirement 1]
- [Requirement 2]

## Deliverables
- [Requirement 1]
- [Requirement 2]

## Success Criteria
- [Requirement 1]
- [Requirement 2]

## Ambiguous Requirements & Assumptions
### Ambiguous Requirements
- [Ambiguous requirement 1] - [Your interpretation]
- [Ambiguous requirement 2] - [Your interpretation]

### Clarifying Questions
- [Question 1]
- [Question 2]

### Assumptions Made
- [Assumption 1]
- [Assumption 2]
```

## Step 9: Validation
Review the extracted requirements to ensure:
- All critical functionality is captured
- No important constraints are missed
- Requirements are specific and actionable
- Time constraints are considered

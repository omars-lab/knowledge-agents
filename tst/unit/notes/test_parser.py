"""
Unit tests for NotePlan markdown parsing.

Tests verify that markdown is correctly parsed into sections (headers) and todos,
with proper hierarchy tracking for tasks under nested sections.
"""

# Add src to path for imports
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from notes.parser import parse_markdown_to_structure

pytestmark = [pytest.mark.unit]


class TestMarkdownParsing:
    """Test basic markdown parsing functionality."""

    def test_empty_markdown(self):
        """Test parsing empty markdown returns empty structure."""
        result = parse_markdown_to_structure("")

        assert result == {"sections": [], "todos": []}

    def test_simple_header(self):
        """Test parsing a single header."""
        markdown = "# Main Section"
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 1
        assert result["sections"][0]["level"] == 1
        assert result["sections"][0]["text"] == "Main Section"
        assert result["sections"][0]["parent_id"] is None
        assert result["sections"][0]["id"] == "section_0"
        assert len(result["todos"]) == 0

    def test_simple_todo(self):
        """Test parsing a single todo without headers."""
        markdown = "- [ ] Task 1"
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 0
        assert len(result["todos"]) == 1
        assert result["todos"][0]["text"] == "Task 1"
        assert result["todos"][0]["completed"] is False
        assert result["todos"][0]["section_ids"] == []

    def test_completed_todo(self):
        """Test parsing a completed todo."""
        markdown = "- [x] Completed task"
        result = parse_markdown_to_structure(markdown)

        assert len(result["todos"]) == 1
        assert result["todos"][0]["text"] == "Completed task"
        assert result["todos"][0]["completed"] is True

    def test_completed_todo_uppercase(self):
        """Test parsing a completed todo with uppercase X."""
        markdown = "- [X] Completed task"
        result = parse_markdown_to_structure(markdown)

        assert len(result["todos"]) == 1
        assert result["todos"][0]["text"] == "Completed task"
        assert result["todos"][0]["completed"] is True

    def test_multiple_todos(self):
        """Test parsing multiple todos."""
        markdown = """
- [ ] Task 1
- [x] Task 2
- [ ] Task 3
"""
        result = parse_markdown_to_structure(markdown)

        assert len(result["todos"]) == 3
        assert result["todos"][0]["text"] == "Task 1"
        assert result["todos"][0]["completed"] is False
        assert result["todos"][1]["text"] == "Task 2"
        assert result["todos"][1]["completed"] is True
        assert result["todos"][2]["text"] == "Task 3"
        assert result["todos"][2]["completed"] is False


class TestHeaderHierarchy:
    """Test header hierarchy parsing."""

    def test_h1_h2_hierarchy(self):
        """Test parsing h1 -> h2 hierarchy."""
        markdown = """
# Level 1
## Level 2
"""
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 2
        assert result["sections"][0]["level"] == 1
        assert result["sections"][0]["text"] == "Level 1"
        assert result["sections"][0]["parent_id"] is None

        assert result["sections"][1]["level"] == 2
        assert result["sections"][1]["text"] == "Level 2"
        assert result["sections"][1]["parent_id"] == result["sections"][0]["id"]

    def test_h1_h2_h3_hierarchy(self):
        """Test parsing h1 -> h2 -> h3 hierarchy."""
        markdown = """
# Level 1
## Level 2
### Level 3
"""
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 3
        assert result["sections"][0]["level"] == 1
        assert result["sections"][0]["parent_id"] is None

        assert result["sections"][1]["level"] == 2
        assert result["sections"][1]["parent_id"] == result["sections"][0]["id"]

        assert result["sections"][2]["level"] == 3
        assert result["sections"][2]["parent_id"] == result["sections"][1]["id"]

    def test_sibling_headers(self):
        """Test parsing sibling headers at the same level."""
        markdown = """
# Section 1
# Section 2
## Subsection
"""
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 3
        assert result["sections"][0]["level"] == 1
        assert result["sections"][0]["text"] == "Section 1"
        assert result["sections"][0]["parent_id"] is None

        assert result["sections"][1]["level"] == 1
        assert result["sections"][1]["text"] == "Section 2"
        assert result["sections"][1]["parent_id"] is None  # Sibling, not child

        assert result["sections"][2]["level"] == 2
        assert result["sections"][2]["text"] == "Subsection"
        assert (
            result["sections"][2]["parent_id"] == result["sections"][1]["id"]
        )  # Child of Section 2

    def test_deep_nesting(self):
        """Test parsing deeply nested headers."""
        markdown = """
# H1
## H2
### H3
#### H4
##### H5
###### H6
"""
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 6
        for i, section in enumerate(result["sections"]):
            assert section["level"] == i + 1
            if i > 0:
                assert section["parent_id"] == result["sections"][i - 1]["id"]

    def test_back_to_higher_level(self):
        """Test parsing when header level goes back up."""
        markdown = """
# H1
## H2
### H3
## H2 Again
"""
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 4
        assert result["sections"][0]["level"] == 1  # H1
        assert result["sections"][1]["level"] == 2  # H2
        assert result["sections"][1]["parent_id"] == result["sections"][0]["id"]
        assert result["sections"][2]["level"] == 3  # H3
        assert result["sections"][2]["parent_id"] == result["sections"][1]["id"]
        assert result["sections"][3]["level"] == 2  # H2 Again
        assert (
            result["sections"][3]["parent_id"] == result["sections"][0]["id"]
        )  # Back to H1 as parent


class TestTodoWithHeaders:
    """Test todos with header hierarchy."""

    def test_todo_under_h1(self):
        """Test todo under a single h1 header."""
        markdown = """
# Main Section
- [ ] Task under h1
"""
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 1
        assert len(result["todos"]) == 1

        todo = result["todos"][0]
        assert todo["text"] == "Task under h1"
        assert todo["section_ids"] == [result["sections"][0]["id"]]

    def test_todo_under_h2(self):
        """Test todo under h1 -> h2 hierarchy."""
        markdown = """
# Main Section
## Subsection
- [ ] Task under h2
"""
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 2
        assert len(result["todos"]) == 1

        todo = result["todos"][0]
        assert todo["text"] == "Task under h2"
        # Should have both h1 and h2 in hierarchy
        assert len(todo["section_ids"]) == 2
        assert todo["section_ids"][0] == result["sections"][0]["id"]  # H1
        assert todo["section_ids"][1] == result["sections"][1]["id"]  # H2

    def test_todo_under_h3(self):
        """Test todo under h1 -> h2 -> h3 hierarchy."""
        markdown = """
# Main Section
## Subsection
### Sub-subsection
- [ ] Task under h3
"""
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 3
        assert len(result["todos"]) == 1

        todo = result["todos"][0]
        assert todo["text"] == "Task under h3"
        # Should have h1, h2, and h3 in hierarchy
        assert len(todo["section_ids"]) == 3
        assert todo["section_ids"][0] == result["sections"][0]["id"]  # H1
        assert todo["section_ids"][1] == result["sections"][1]["id"]  # H2
        assert todo["section_ids"][2] == result["sections"][2]["id"]  # H3

    def test_multiple_todos_different_sections(self):
        """Test todos under different sections."""
        markdown = """
# Section 1
- [ ] Task 1

## Subsection 1.1
- [ ] Task 2

# Section 2
- [ ] Task 3
"""
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 3
        assert len(result["todos"]) == 3

        # Task 1: under Section 1
        assert result["todos"][0]["text"] == "Task 1"
        assert result["todos"][0]["section_ids"] == [result["sections"][0]["id"]]

        # Task 2: under Section 1 -> Subsection 1.1
        assert result["todos"][1]["text"] == "Task 2"
        assert len(result["todos"][1]["section_ids"]) == 2
        assert result["todos"][1]["section_ids"][0] == result["sections"][0]["id"]
        assert result["todos"][1]["section_ids"][1] == result["sections"][1]["id"]

        # Task 3: under Section 2
        assert result["todos"][2]["text"] == "Task 3"
        assert result["todos"][2]["section_ids"] == [result["sections"][2]["id"]]

    def test_todos_without_headers(self):
        """Test todos that appear before any headers."""
        markdown = """
- [ ] Task before headers
# Section 1
- [ ] Task after header
"""
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 1
        assert len(result["todos"]) == 2

        # First todo has no section
        assert result["todos"][0]["text"] == "Task before headers"
        assert result["todos"][0]["section_ids"] == []

        # Second todo has section
        assert result["todos"][1]["text"] == "Task after header"
        assert result["todos"][1]["section_ids"] == [result["sections"][0]["id"]]


class TestRealWorldScenarios:
    """Test real-world NotePlan daily plan scenarios."""

    def test_daily_plan_structure(self):
        """Test a typical daily plan structure."""
        markdown = """
# Morning Routine
## Exercise
- [ ] Go for a run
- [x] Stretch
## Breakfast
- [ ] Make coffee
- [ ] Eat breakfast

# Work Tasks
## Important
- [ ] Review PRs
- [ ] Write documentation
## Meetings
- [x] Standup
- [ ] Team sync

# Evening
- [ ] Read book
- [ ] Plan tomorrow
"""
        result = parse_markdown_to_structure(markdown)

        # Should have 5 sections: Morning Routine, Exercise, Breakfast, Work Tasks, Important, Meetings, Evening
        # Actually, let me count: H1 Morning Routine, H2 Exercise, H2 Breakfast, H1 Work Tasks, H2 Important, H2 Meetings, H1 Evening
        assert len(result["sections"]) == 7
        assert len(result["todos"]) == 8

        # Verify section hierarchy
        morning_routine = result["sections"][0]
        assert morning_routine["text"] == "Morning Routine"
        assert morning_routine["level"] == 1

        exercise = result["sections"][1]
        assert exercise["text"] == "Exercise"
        assert exercise["level"] == 2
        assert exercise["parent_id"] == morning_routine["id"]

        # Verify todos have correct hierarchy
        todos_by_text = {todo["text"]: todo for todo in result["todos"]}

        # Todo under Exercise should have Morning Routine and Exercise
        run_todo = todos_by_text["Go for a run"]
        assert len(run_todo["section_ids"]) == 2
        assert run_todo["section_ids"][0] == morning_routine["id"]
        assert run_todo["section_ids"][1] == exercise["id"]
        assert run_todo["completed"] is False

        # Completed todo
        stretch_todo = todos_by_text["Stretch"]
        assert stretch_todo["completed"] is True

        # Todo under Work Tasks -> Important should have Work Tasks and Important
        work_tasks = [s for s in result["sections"] if s["text"] == "Work Tasks"][0]
        important = [s for s in result["sections"] if s["text"] == "Important"][0]

        review_todo = todos_by_text["Review PRs"]
        assert len(review_todo["section_ids"]) == 2
        assert review_todo["section_ids"][0] == work_tasks["id"]
        assert review_todo["section_ids"][1] == important["id"]

    def test_mixed_completed_and_incomplete(self):
        """Test mix of completed and incomplete todos."""
        markdown = """
# Tasks
- [x] Done task 1
- [ ] Pending task
- [x] Done task 2
- [ ] Another pending
- [X] Done task 3 (uppercase)
"""
        result = parse_markdown_to_structure(markdown)

        assert len(result["todos"]) == 5
        assert result["todos"][0]["completed"] is True
        assert result["todos"][1]["completed"] is False
        assert result["todos"][2]["completed"] is True
        assert result["todos"][3]["completed"] is False
        assert result["todos"][4]["completed"] is True

    def test_complex_nested_structure(self):
        """Test a complex nested structure with multiple levels."""
        markdown = """
# Project Alpha
## Phase 1
### Planning
- [ ] Create plan
- [x] Get approval
### Execution
- [ ] Start implementation
## Phase 2
- [ ] Review Phase 1
# Project Beta
- [ ] Initial setup
"""
        result = parse_markdown_to_structure(markdown)

        # Sections: Project Alpha, Phase 1, Planning, Execution, Phase 2, Project Beta
        assert len(result["sections"]) == 6
        assert len(result["todos"]) == 5

        # Find sections
        project_alpha = [s for s in result["sections"] if s["text"] == "Project Alpha"][
            0
        ]
        phase_1 = [s for s in result["sections"] if s["text"] == "Phase 1"][0]
        planning = [s for s in result["sections"] if s["text"] == "Planning"][0]

        todos_by_text = {todo["text"]: todo for todo in result["todos"]}

        # Todo under Planning should have Project Alpha, Phase 1, Planning
        create_plan = todos_by_text["Create plan"]
        assert len(create_plan["section_ids"]) == 3
        assert create_plan["section_ids"][0] == project_alpha["id"]
        assert create_plan["section_ids"][1] == phase_1["id"]
        assert create_plan["section_ids"][2] == planning["id"]

        # Todo under Phase 2 should have Project Alpha, Phase 2
        review = todos_by_text["Review Phase 1"]
        phase_2 = [s for s in result["sections"] if s["text"] == "Phase 2"][0]
        assert len(review["section_ids"]) == 2
        assert review["section_ids"][0] == project_alpha["id"]
        assert review["section_ids"][1] == phase_2["id"]


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_whitespace_only(self):
        """Test markdown with only whitespace."""
        markdown = "   \n\n  \t  \n"
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 0
        assert len(result["todos"]) == 0

    def test_todo_with_extra_spaces(self):
        """Test todo with extra spaces."""
        markdown = "- [ ]   Task with spaces   "
        result = parse_markdown_to_structure(markdown)

        assert len(result["todos"]) == 1
        assert result["todos"][0]["text"] == "Task with spaces"

    def test_todo_without_text(self):
        """Test todo marker without text."""
        markdown = "- [ ]"
        result = parse_markdown_to_structure(markdown)

        # Should not create a todo if there's no text
        assert len(result["todos"]) == 0

    def test_header_with_whitespace(self):
        """Test header with extra whitespace."""
        markdown = "#   Header with spaces   "
        result = parse_markdown_to_structure(markdown)

        assert len(result["sections"]) == 1
        assert result["sections"][0]["text"] == "Header with spaces"

    def test_regular_list_items_not_todos(self):
        """Test that regular list items (without [ ]) are not treated as todos."""
        markdown = """
- Regular item 1
- Regular item 2
- [ ] This is a todo
"""
        result = parse_markdown_to_structure(markdown)

        # Only the item with [ ] should be a todo
        assert len(result["todos"]) == 1
        assert result["todos"][0]["text"] == "This is a todo"

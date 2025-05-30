import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from tools.list_notes import action

def test_action_no_notes():
    # Test when no notes are found
    with patch('tools.list_notes.Path.glob') as mock_glob:
        mock_glob.return_value = []
        result = action()

        assert "📭 No notes found." in result
        mock_glob.assert_called_once_with("*.md")

def test_action_with_notes():
    # Test when notes are found
    with patch('tools.list_notes.Path.glob') as mock_glob, \
         patch('tools.list_notes.sorted') as mock_sorted:
        # Create mock Path objects for the note files
        mock_files = [
            MagicMock(spec=Path, name="2025-05-28.md"),
            MagicMock(spec=Path, name="2025-05-29.md"),
            MagicMock(spec=Path, name="2025-05-30.md"),
        ]

        # Set the name attribute for each mock
        for i, mock_file in enumerate(mock_files):
            mock_file.name = f"2025-05-{28+i}.md"

        mock_glob.return_value = mock_files
        # Make sorted return the same list (we're not testing the sorting)
        mock_sorted.return_value = mock_files

        result = action()

        assert "🗒️ Your notes:" in result
        assert "- 2025-05-28.md" in result
        assert "- 2025-05-29.md" in result
        assert "- 2025-05-30.md" in result
        mock_glob.assert_called_once_with("*.md")
        mock_sorted.assert_called_once_with(mock_files)

def test_action_with_many_notes():
    # Test when more than 5 notes are found (should only show the latest 5)
    with patch('tools.list_notes.Path.glob') as mock_glob, \
         patch('tools.list_notes.sorted') as mock_sorted:
        # Create mock Path objects for the note files
        mock_files = [
            MagicMock(spec=Path, name="2025-05-25.md"),
            MagicMock(spec=Path, name="2025-05-26.md"),
            MagicMock(spec=Path, name="2025-05-27.md"),
            MagicMock(spec=Path, name="2025-05-28.md"),
            MagicMock(spec=Path, name="2025-05-29.md"),
            MagicMock(spec=Path, name="2025-05-30.md"),
            MagicMock(spec=Path, name="2025-05-31.md"),
        ]

        # Set the name attribute for each mock
        for i, mock_file in enumerate(mock_files):
            mock_file.name = f"2025-05-{25+i}.md"

        mock_glob.return_value = mock_files
        # Make sorted return the same list (we're not testing the sorting)
        mock_sorted.return_value = mock_files

        result = action()

        # Should only include the latest 5 files
        assert "🗒️ Your notes:" in result
        assert "- 2025-05-27.md" in result
        assert "- 2025-05-28.md" in result
        assert "- 2025-05-29.md" in result
        assert "- 2025-05-30.md" in result
        assert "- 2025-05-31.md" in result

        # Should not include the oldest files
        assert "- 2025-05-25.md" not in result
        assert "- 2025-05-26.md" not in result

        mock_glob.assert_called_once_with("*.md")
        mock_sorted.assert_called_once_with(mock_files)

import sys
import types
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

# Helper function to create Windows-compatible paths
def win_path(path_str):
    """Convert a path string to a Windows-compatible Path object."""
    # Replace forward slashes with backslashes
    return Path(path_str.replace('/', '\\'))

# Mock external dependencies before importing the module under test
@pytest.fixture(scope="module", autouse=True)
def mock_dependencies():
    """Mock all external dependencies for project_detector.py before import."""
    # Mock langchain and related modules
    sys.modules['langchain_community'] = MagicMock()
    sys.modules['langchain_community.vectorstores'] = MagicMock()
    sys.modules['langchain_community.embeddings'] = types.ModuleType("langchain_community.embeddings")
    sys.modules['langchain_community.vectorstores.FAISS'] = MagicMock()

    # Mock torch and related modules
    sys.modules['torch'] = MagicMock()
    sys.modules['sentence_transformers'] = MagicMock()
    sys.modules['sentence_transformers.SentenceTransformer'] = MagicMock()

    # Mock huggingface modules
    huggingface_mod = types.ModuleType("langchain_huggingface")
    huggingface_mod.HuggingFaceEmbeddings = MagicMock()
    sys.modules['langchain_huggingface'] = huggingface_mod

    # Mock other dependencies
    sys.modules['faiss'] = MagicMock()
    #sys.modules['numpy'] = MagicMock()

    yield


class TestDetectJavaScriptProject:
    """Tests for the detect_javascript_project function"""

    def test_detect_javascript_project_with_valid_package_json(self):
        """Test detecting a JavaScript project with a valid package.json file."""
        from engine import project_detector

        # Mock package.json content
        package_json_content = json.dumps({
            "name": "test-project",
            "version": "1.0.0",
            "description": "Test JavaScript project",
            "main": "index.js",
            "author": "Test Author",
            "license": "MIT"
        })

        # Mock Path.exists and open function
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=package_json_content)):

            # Call the function
            result = project_detector.detect_javascript_project(Path("/fake/project/path"))

            # Verify the result
            assert result is not None
            assert result["project_type"] == "javascript"
            assert result["name"] == "test-project"
            assert result["version"] == "1.0.0"
            assert result["description"] == "Test JavaScript project"
            assert result["main"] == "index.js"
            assert result["author"] == "Test Author"
            assert result["license"] == "MIT"

    def test_detect_javascript_project_without_package_json(self):
        """Test detecting a JavaScript project without a package.json file."""
        from engine import project_detector

        # Mock Path.exists to return False
        with patch('pathlib.Path.exists', return_value=False):

            # Call the function
            result = project_detector.detect_javascript_project(Path("/fake/project/path"))

            # Verify the result
            assert result is None

    def test_detect_javascript_project_with_invalid_package_json(self):
        """Test detecting a JavaScript project with an invalid package.json file."""
        from engine import project_detector

        # Mock Path.exists to return True but open to raise an exception
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', side_effect=Exception("Test exception")):

            # Call the function
            result = project_detector.detect_javascript_project(Path("/fake/project/path"))

            # Verify the result
            assert result is None


class TestDetectTypeScriptProject:
    """Tests for the detect_typescript_project function"""

    def test_detect_typescript_project_with_valid_tsconfig_json(self):
        """Test detecting a TypeScript project with a valid tsconfig.json file."""
        from engine import project_detector

        # Mock tsconfig.json content
        tsconfig_json_content = json.dumps({
            "compilerOptions": {
                "target": "es6",
                "module": "commonjs"
            },
            "include": ["src/**/*"],
            "exclude": ["node_modules"]
        })

        # Mock package.json content for the JavaScript part
        package_json_content = json.dumps({
            "name": "test-ts-project",
            "version": "1.0.0"
        })

        # Create a custom mock for open that returns different content based on the file
        def mock_open_file(file, *args, **kwargs):
            file_str = str(file)
            if file_str.endswith("tsconfig.json"):
                return mock_open(read_data=tsconfig_json_content)()
            elif file_str.endswith("package.json"):
                return mock_open(read_data=package_json_content)()
            return mock_open()()

        # Mock Path.exists to always return True and open function to return appropriate content
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', side_effect=mock_open_file):

            # Call the function
            result = project_detector.detect_typescript_project(Path("/fake/project/path"))

            # Verify the result
            assert result is not None
            assert result["project_type"] == "typescript"
            assert result["name"] == "test-ts-project"
            assert result["version"] == "1.0.0"
            assert "compiler_options" in result
            assert result["compiler_options"]["target"] == "es6"
            assert result["include"] == ["src/**/*"]
            assert result["exclude"] == ["node_modules"]

    def test_detect_typescript_project_without_tsconfig_json(self):
        """Test detecting a TypeScript project without a tsconfig.json file."""
        from engine import project_detector

        # Mock Path.exists to return False for tsconfig.json
        with patch('pathlib.Path.exists', return_value=False):

            # Call the function
            result = project_detector.detect_typescript_project(Path("/fake/project/path"))

            # Verify the result
            assert result is None


class TestDetectPythonProject:
    """Tests for the detect_python_project function"""

    def test_detect_python_project_with_pyproject_toml(self):
        """Test detecting a Python project with a pyproject.toml file."""
        from engine import project_detector

        # Mock pyproject.toml content
        pyproject_toml_content = """
[build-system]
requires = ["setuptools>=42", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "test-python-project"
version = "0.1.0"
description = "A test Python project"
        """

        def exists_side_effect(self):
            # Only True for pyproject.toml, else False
            return str(self).endswith("pyproject.toml")
        # Mock Path.exists to return True for pyproject.toml
        with patch('pathlib.Path.exists', new=exists_side_effect), \
                patch('builtins.open', mock_open(read_data=pyproject_toml_content)):

            # Call the function
            result = project_detector.detect_python_project(Path("/fake/project/path"))

            # Verify the result
            assert result is not None
            assert result["project_type"] == "python"
            assert result["has_pyproject_toml"] is True
            assert result["has_requirements_txt"] is False
            assert result["has_setup_py"] is False

    def test_detect_python_project_with_requirements_txt(self):
        """Test detecting a Python project with a requirements.txt file."""
        from engine import project_detector

        # Mock requirements.txt content
        requirements_txt_content = """
pytest==7.0.0
black==22.1.0
# This is a comment
flask>=2.0.0
        """

        def exists_side_effect(self):
            return str(self).endswith("requirements.txt")
        # Mock Path.exists to return True for requirements.txt
        with patch('pathlib.Path.exists', new=exists_side_effect), \
                patch('builtins.open', mock_open(read_data=requirements_txt_content)):

            # Call the function
            result = project_detector.detect_python_project(Path("/fake/project/path"))

            # Verify the result
            assert result is not None
            assert result["project_type"] == "python"
            assert result["has_pyproject_toml"] is False
            assert result["has_requirements_txt"] is True
            assert result["has_setup_py"] is False
            assert "dependencies" in result
            assert len(result["dependencies"]) == 3  # Excluding the comment

    def test_detect_python_project_without_python_files(self):
        """Test detecting a Python project without any Python project files."""
        from engine import project_detector

        # Mock Path.exists to return False for all Python project files
        with patch('pathlib.Path.exists', return_value=False):

            # Call the function
            result = project_detector.detect_python_project(Path("/fake/project/path"))

            # Verify the result
            assert result is None


class TestGetFileList:
    """Tests for the get_file_list function"""

    def test_get_file_list_with_files(self):
        """Test getting a list of files from a project directory."""
        from engine import project_detector

        # Mock files in the project directory
        mock_files = [
            Path("/fake/project/path/file1.txt"),
            Path("/fake/project/path/file2.py"),
            Path("/fake/project/path/src/file3.js")
        ]

        # Mock Path.iterdir to return the mock files
        def mock_iterdir(path):
            path_str = path.as_posix()

            if str(path_str) == "/fake/project/path":
                return [mock_files[0], mock_files[1], Path("/fake/project/path/src")]
            elif str(path_str) == "/fake/project/path/src":
                return [mock_files[2]]
            return []

        def is_file_side_effect(p):
            # These are files:
            path_str = p.as_posix()
            return str(path_str) in [
                "/fake/project/path/file1.txt",
                "/fake/project/path/file2.py",
                "/fake/project/path/src/file3.js"
            ]

        def is_dir_side_effect(p):
            path_str = p.as_posix()
            # Only the src dir is a directory
            return str(path_str) == "/fake/project/path/src"

        def relative_to_side_effect(self, other):
            # Remove the root prefix and slash, return as Path
            # Supports both POSIX and Windows
            prefix = other.as_posix()
            return Path(self.as_posix()[len(prefix) + 1:])

        # Mock Path methods
        with patch('pathlib.Path.iterdir', side_effect=mock_iterdir, autospec=True), \
                patch('pathlib.Path.is_file', side_effect=is_file_side_effect, autospec=True), \
                patch('pathlib.Path.is_dir', side_effect=is_dir_side_effect, autospec=True), \
                patch('pathlib.Path.relative_to', side_effect=relative_to_side_effect, autospec=True):

            # Call the function
            result = [Path(f).as_posix() for f in project_detector.get_file_list(Path("/fake/project/path"))]

            # Verify the result
            assert len(result) == 3
            assert "file1.txt" in result
            assert "file2.py" in result
            assert "src/file3.js" in result

    def test_get_file_list_with_ignored_directories(self):
        from engine import project_detector

        mock_files = [
            Path("/fake/project/path/file1.txt"),
            Path("/fake/project/path/.git/config"),
            Path("/fake/project/path/node_modules/package.json")
        ]

        def mock_iterdir(self):
            path_str = self.as_posix()
            if path_str == "/fake/project/path":
                return [mock_files[0], Path("/fake/project/path/.git"), Path("/fake/project/path/node_modules")]
            elif path_str == "/fake/project/path/.git":
                return [mock_files[1]]
            elif path_str == "/fake/project/path/node_modules":
                return [mock_files[2]]
            return []

        def is_file_side_effect(p):
            path_str = p.as_posix()
            # Only the regular file is a file
            return path_str == "/fake/project/path/file1.txt"

        def is_dir_side_effect(p):
            path_str = p.as_posix()
            # Only .git and node_modules are dirs
            return path_str in [
                "/fake/project/path/.git",
                "/fake/project/path/node_modules"
            ]

        def relative_to_side_effect(self, other):
            # Remove the root prefix + slash, return as Path
            prefix = other.as_posix()
            return Path(self.as_posix()[len(prefix) + 1:])

        with patch('pathlib.Path.iterdir', side_effect=mock_iterdir, autospec=True), \
                patch('pathlib.Path.is_file', side_effect=is_file_side_effect, autospec=True), \
                patch('pathlib.Path.is_dir', side_effect=is_dir_side_effect, autospec=True), \
                patch('pathlib.Path.relative_to', side_effect=relative_to_side_effect, autospec=True):

            result = project_detector.get_file_list(Path("/fake/project/path"))
            # Normalize all returned results to POSIX
            result = [Path(f).as_posix() for f in result]
            assert len(result) == 1
            assert "file1.txt" in result
            assert ".git/config" not in result
            assert "node_modules/package.json" not in result

class TestAskLLMForProjectType:
    """Tests for the ask_llm_for_project_type function"""

    @patch('engine.di.container.get_typed')
    def test_ask_llm_for_project_type_success(self, mock_get_typed):
        """Test asking the LLM for project type with a successful response."""
        from engine import project_detector
        from engine.interfaces import LLMBackendInterface

        # Create a mock LLM backend
        mock_llm_backend = MagicMock(spec=LLMBackendInterface)
        mock_llm_backend.query.return_value = """```json
{
  "project_type": "python",
  "confidence": 0.95,
  "reasoning": "The presence of requirements.txt and setup.py indicates a Python project."
}
```"""

        # Set up the mock to return our mock LLM backend
        mock_get_typed.return_value = mock_llm_backend

        # Call the function
        result = project_detector.ask_llm_for_project_type(
            Path("/fake/project/path"),
            ["requirements.txt", "setup.py", "main.py"]
        )

        # Verify the result
        assert result is not None
        assert result["project_type"] == "python"
        assert result["llm_confidence"] == 0.95
        assert "The presence of requirements.txt" in result["llm_reasoning"]

        # Verify the LLM was called with the expected arguments
        mock_get_typed.assert_called_once()
        mock_llm_backend.query.assert_called_once()
        # Check that the prompt contains the file list
        prompt_arg = mock_llm_backend.query.call_args[0][0]
        assert "requirements.txt" in prompt_arg
        assert "setup.py" in prompt_arg
        assert "main.py" in prompt_arg

    @patch('engine.di.container.get_typed')
    def test_ask_llm_for_project_type_no_backend(self, mock_get_typed):
        """Test asking the LLM for project type when no backend is available."""
        from engine import project_detector

        # Set up the mock to return None (no backend available)
        mock_get_typed.return_value = None

        # Call the function
        result = project_detector.ask_llm_for_project_type(
            Path("/fake/project/path"),
            ["file1.txt", "file2.js"]
        )

        # Verify the result
        assert result is not None
        assert result["project_type"] == "unknown"
        assert Path(result["path"]).as_posix() == "/fake/project/path"
        assert result["name"] == "path"  # The name is the last part of the path

    @patch('engine.di.container.get_typed')
    def test_ask_llm_for_project_type_invalid_response(self, mock_get_typed):
        """Test asking the LLM for project type with an invalid response."""
        from engine import project_detector
        from engine.interfaces import LLMBackendInterface

        # Create a mock LLM backend with an invalid JSON response
        mock_llm_backend = MagicMock(spec=LLMBackendInterface)
        mock_llm_backend.query.return_value = "This is not valid JSON"

        # Set up the mock to return our mock LLM backend
        mock_get_typed.return_value = mock_llm_backend

        # Call the function
        result = project_detector.ask_llm_for_project_type(
            Path("/fake/project/path"),
            ["file1.txt", "file2.js"]
        )

        # Verify the result
        assert result is not None
        assert result["project_type"] == "unknown"
        assert "llm_error" in result
        assert "llm_raw_response" in result
        assert result["llm_raw_response"] == "This is not valid JSON"


class TestDetectProjectType:
    """Tests for the detect_project_type function"""

    @patch('engine.project_detector.detect_typescript_project')
    @patch('engine.project_detector.detect_javascript_project')
    @patch('engine.project_detector.detect_python_project')
    def test_detect_project_type_typescript(self, mock_detect_python, mock_detect_javascript, mock_detect_typescript):
        """Test detecting a TypeScript project."""
        from engine import project_detector

        # Set up the mocks to simulate a TypeScript project
        mock_detect_typescript.return_value = {"project_type": "typescript", "name": "test-project"}
        mock_detect_javascript.return_value = None
        mock_detect_python.return_value = None

        # Call the function
        result = project_detector.detect_project_type(Path("/fake/project/path"))

        # Verify the result
        assert result is not None
        assert result["project_type"] == "typescript"
        assert result["name"] == "test-project"

        # Verify the detectors were called in the expected order
        mock_detect_typescript.assert_called_once()
        mock_detect_javascript.assert_not_called()  # Should not be called since TypeScript was detected
        mock_detect_python.assert_not_called()  # Should not be called since TypeScript was detected

    @patch('engine.project_detector.detect_typescript_project')
    @patch('engine.project_detector.detect_javascript_project')
    @patch('engine.project_detector.detect_python_project')
    @patch('engine.project_detector.get_file_list')
    @patch('engine.project_detector.ask_llm_for_project_type')
    def test_detect_project_type_unknown_with_llm(self, mock_ask_llm, mock_get_file_list,
                                                 mock_detect_python, mock_detect_javascript, mock_detect_typescript):
        """Test detecting an unknown project type with LLM fallback."""
        from engine import project_detector

        # Set up the mocks to simulate an unknown project type
        mock_detect_typescript.return_value = None
        mock_detect_javascript.return_value = None
        mock_detect_python.return_value = None

        # Set up the file list and LLM response
        mock_get_file_list.return_value = ["file1.go", "file2.go"]
        mock_ask_llm.return_value = {"project_type": "go", "llm_confidence": 0.9}

        # Call the function
        result = project_detector.detect_project_type(Path("/fake/project/path"))

        # Verify the result
        assert result is not None
        assert result["project_type"] == "go"
        assert result["llm_confidence"] == 0.9

        # Verify all detectors were called
        mock_detect_typescript.assert_called_once()
        mock_detect_javascript.assert_called_once()
        mock_detect_python.assert_called_once()
        mock_get_file_list.assert_called_once()
        mock_ask_llm.assert_called_once()

    @patch('engine.project_detector.detect_typescript_project')
    @patch('engine.project_detector.detect_javascript_project')
    @patch('engine.project_detector.detect_python_project')
    @patch('engine.project_detector.get_file_list')
    @patch('engine.project_detector.ask_llm_for_project_type')
    def test_detect_project_type_completely_unknown(self, mock_ask_llm, mock_get_file_list,
                                                  mock_detect_python, mock_detect_javascript, mock_detect_typescript):
        """Test detecting a completely unknown project type."""
        from engine import project_detector

        # Set up the mocks to simulate an unknown project type
        mock_detect_typescript.return_value = None
        mock_detect_javascript.return_value = None
        mock_detect_python.return_value = None

        # Set up the file list and LLM response
        mock_get_file_list.return_value = ["file1.txt", "file2.txt"]
        mock_ask_llm.return_value = {"project_type": "unknown"}

        # Call the function
        result = project_detector.detect_project_type(Path("/fake/project/path"))

        # Verify the result
        assert result is not None
        assert result["project_type"] == "unknown"
        assert Path(result["path"]).as_posix() == "/fake/project/path"
        assert result["name"] == "path"  # The name is the last part of the path

        # Verify all detectors were called
        mock_detect_typescript.assert_called_once()
        mock_detect_javascript.assert_called_once()
        mock_detect_python.assert_called_once()
        mock_get_file_list.assert_called_once()
        mock_ask_llm.assert_called_once()

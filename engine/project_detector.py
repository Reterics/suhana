"""
Project Detector for Suhana AI Assistant

This module provides functionality to detect project types and extract metadata
from project files. It supports JavaScript, TypeScript, and Python projects.
"""
from pathlib import Path
import json
from typing import Dict, Any, Optional, List, Tuple

from engine.di import container
from engine.interfaces import LLMBackendInterface

def detect_javascript_project(project_path: Path) -> Optional[Dict[str, Any]]:
    """
    Detect a JavaScript project and extract metadata from package.json.

    Args:
        project_path: Path to the project directory

    Returns:
        Dictionary containing project metadata or None if not a JavaScript project
    """
    package_json_path = project_path / "package.json"
    if not package_json_path.exists():
        return None

    try:
        with open(package_json_path, "r", encoding="utf-8") as f:
            package_data = json.load(f)

        metadata = {
            "project_type": "javascript",
            "name": package_data.get("name", ""),
            "version": package_data.get("version", ""),
            "description": package_data.get("description", ""),
            "main": package_data.get("main", ""),
            "author": package_data.get("author", ""),
            "license": package_data.get("license", ""),
        }

        return metadata
    except Exception as e:
        print(f"Error parsing package.json: {e}")
        return None

def detect_typescript_project(project_path: Path) -> Optional[Dict[str, Any]]:
    """
    Detect a TypeScript project and extract metadata from tsconfig.json and package.json.

    Args:
        project_path: Path to the project directory

    Returns:
        Dictionary containing project metadata or None if not a TypeScript project
    """
    tsconfig_path = project_path / "tsconfig.json"
    if not tsconfig_path.exists():
        return None

    # First get basic metadata from package.json if it exists
    js_metadata = detect_javascript_project(project_path)

    try:
        with open(tsconfig_path, "r", encoding="utf-8") as f:
            tsconfig_data = json.load(f)

        metadata = js_metadata or {}
        metadata.update({
            "project_type": "typescript",
            "compiler_options": tsconfig_data.get("compilerOptions", {}),
            "include": tsconfig_data.get("include", []),
            "exclude": tsconfig_data.get("exclude", []),
        })

        return metadata
    except Exception as e:
        print(f"Error parsing tsconfig.json: {e}")
        return js_metadata  # Return JS metadata if we have it, even if TS parsing failed

def detect_python_project(project_path: Path) -> Optional[Dict[str, Any]]:
    """
    Detect a Python project and extract metadata from pyproject.toml or requirements.txt.

    Args:
        project_path: Path to the project directory

    Returns:
        Dictionary containing project metadata or None if not a Python project
    """
    pyproject_path = project_path / "pyproject.toml"
    requirements_path = project_path / "requirements.txt"
    setup_py_path = project_path / "setup.py"

    # Check if any Python project files exist
    if not any(p.exists() for p in [pyproject_path, requirements_path, setup_py_path]):
        return None

    metadata = {
        "project_type": "python",
        "has_pyproject_toml": pyproject_path.exists(),
        "has_requirements_txt": requirements_path.exists(),
        "has_setup_py": setup_py_path.exists(),
    }

    # Extract metadata from pyproject.toml if it exists
    if pyproject_path.exists():
        try:
            # We don't use toml.load here to avoid adding a dependency
            # Instead, we'll parse it manually for basic metadata
            with open(pyproject_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract project name
            name_match = content.find('name = "')
            if name_match != -1:
                name_start = name_match + 8
                name_end = content.find('"', name_start)
                if name_end != -1:
                    metadata["name"] = content[name_start:name_end]

            # Extract version
            version_match = content.find('version = "')
            if version_match != -1:
                version_start = version_match + 11
                version_end = content.find('"', version_start)
                if version_end != -1:
                    metadata["version"] = content[version_start:version_end]

            # Extract description
            description_match = content.find('description = "')
            if description_match != -1:
                description_start = description_match + 15
                description_end = content.find('"', description_start)
                if description_end != -1:
                    metadata["description"] = content[description_start:description_end]
        except Exception as e:
            print(f"Error parsing pyproject.toml: {e}")

    # Extract dependencies from requirements.txt if it exists
    if requirements_path.exists():
        try:
            with open(requirements_path, "r", encoding="utf-8") as f:
                requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            metadata["dependencies"] = requirements
        except Exception as e:
            print(f"Error parsing requirements.txt: {e}")

    return metadata

def get_file_list(project_path: Path, max_files: int = 100, max_depth: int = 3) -> List[str]:
    """
    Get a list of files in the project directory.

    Args:
        project_path: Path to the project directory
        max_files: Maximum number of files to include
        max_depth: Maximum directory depth to traverse

    Returns:
        List of file paths relative to the project directory
    """
    file_list = []
    ignored_dirs = {'.git', 'node_modules', 'venv', '.venv', '__pycache__', 'dist', 'build'}

    def should_ignore(path: Path) -> bool:
        return any(ignored in path.parts for ignored in ignored_dirs)

    def traverse(path: Path, current_depth: int = 0):
        if current_depth > max_depth or len(file_list) >= max_files:
            return

        try:
            for item in path.iterdir():
                if should_ignore(item):
                    continue

                if item.is_file():
                    file_list.append(str(item.relative_to(project_path)))
                    if len(file_list) >= max_files:
                        return
                elif item.is_dir():
                    traverse(item, current_depth + 1)
        except (PermissionError, OSError):
            # Skip directories we can't access
            pass

    traverse(project_path)
    return file_list

def ask_llm_for_project_type(project_path: Path, file_list: List[str]) -> Dict[str, Any]:
    """
    Ask the LLM to determine the project type based on the file list.

    Args:
        project_path: Path to the project directory
        file_list: List of files in the project directory

    Returns:
        Dictionary containing project metadata
    """
    # Get the LLM backend
    backend_name = "ollama_backend"  # Default to ollama
    llm_backend = container.get_typed(backend_name, LLMBackendInterface)

    if not llm_backend:
        return {
            "project_type": "unknown",
            "path": str(project_path),
            "name": project_path.name,
        }

    # Prepare the prompt
    file_list_str = "\n".join(file_list[:50])  # Limit to first 50 files to avoid token limits
    prompt = f"""Based on the following file list from a project directory, determine the most likely project type.
Consider the file extensions, directory structure, and common project files.
Return your answer as a JSON object with the following fields:
- project_type: The type of the project (e.g., python, javascript, typescript, java, rust, go, etc.)
- confidence: A number between 0 and 1 indicating your confidence in the determination
- reasoning: A brief explanation of your reasoning

File list:
{file_list_str}

JSON response:"""

    # Query the LLM
    try:
        system_prompt = "You are a helpful assistant that specializes in identifying project types based on file lists. Respond only with the requested JSON format."
        profile = {}  # Empty profile for this purpose
        settings = {"llm_model": "llama3"}  # Default model

        response = llm_backend.query(prompt, system_prompt, profile, settings)

        # Try to parse the response as JSON
        try:
            import re
            # Extract JSON from the response if it's wrapped in markdown code blocks or other text
            json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', response, re.DOTALL)
            if json_match:
                response_json = json.loads(json_match.group(1))
            else:
                # Try to find any JSON-like structure
                json_match = re.search(r'({.*})', response, re.DOTALL)
                if json_match:
                    response_json = json.loads(json_match.group(1))
                else:
                    # Just try to parse the whole response
                    response_json = json.loads(response)

            # Create metadata from the response
            metadata = {
                "project_type": response_json.get("project_type", "unknown"),
                "path": str(project_path),
                "name": project_path.name,
                "llm_confidence": response_json.get("confidence", 0.0),
                "llm_reasoning": response_json.get("reasoning", ""),
            }
            return metadata
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            print(f"Error parsing LLM response: {e}")
            # Fall back to unknown
            return {
                "project_type": "unknown",
                "path": str(project_path),
                "name": project_path.name,
                "llm_error": str(e),
                "llm_raw_response": response,
            }
    except Exception as e:
        print(f"Error querying LLM: {e}")
        return {
            "project_type": "unknown",
            "path": str(project_path),
            "name": project_path.name,
            "error": str(e),
        }

def detect_project_type(project_path: Path) -> Dict[str, Any]:
    """
    Detect the type of project and extract metadata.

    Args:
        project_path: Path to the project directory

    Returns:
        Dictionary containing project metadata
    """
    # Try to detect each project type
    detectors = [
        detect_typescript_project,  # TypeScript first as it's more specific than JavaScript
        detect_javascript_project,
        detect_python_project,
    ]

    for detector in detectors:
        metadata = detector(project_path)
        if metadata:
            return metadata

    # If no specific project type is detected, try asking the LLM
    file_list = get_file_list(project_path)
    if file_list:
        llm_metadata = ask_llm_for_project_type(project_path, file_list)
        if llm_metadata.get("project_type") != "unknown" or "llm_raw_response" in llm_metadata:
            return llm_metadata

    # If LLM couldn't determine the project type or there was an error, return generic metadata
    return {
        "project_type": "unknown",
        "path": str(project_path),
        "name": project_path.name,
    }

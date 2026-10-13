import os
from pathlib import Path


ALLOWED_EXTENSIONS = {
    ".py",
    ".md",
    ".toml",
    ".json",
}

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
}

MAX_FILE_BYTES = 16_000
MAX_FILES = 100


def list_files(repo_root: Path) -> dict:
    root = repo_root.resolve()
    files = []

    for directory, dirs, names in os.walk(root):
        dirs[:] = [
            name for name in dirs
            if name not in EXCLUDED_DIRS
            and not name.startswith(".")
            and not (Path(directory) / name).is_symlink()
        ]

        for name in sorted(names):
            path = Path(directory) / name

            if name.startswith("."):
                continue

            if path.suffix not in ALLOWED_EXTENSIONS:
                continue

            if path.is_symlink():
                continue

            if not path.resolve().is_relative_to(root):
                continue

            files.append(path.relative_to(root).as_posix())

            if len(files) >= MAX_FILES:
                return {
                    "ok": True,
                    "files": files,
                    "truncated": True,
                }

    return {
        "ok": True,
        "files": files,
        "truncated": False,
    }


def read_file(repo_root: Path, relative_path: str) -> dict:
    root = repo_root.resolve()

    if not isinstance(relative_path, str):
        return {"ok": False, "error": "Invalid path"}

    requested = Path(relative_path)

    if requested.is_absolute() or ".." in requested.parts:
        return {"ok": False, "error": "Path not permitted"}

    if any(
        part.startswith(".") or part in EXCLUDED_DIRS
        for part in requested.parts
    ):
        return {"ok": False, "error": "Excluded path"}

    if requested.suffix not in ALLOWED_EXTENSIONS:
        return {"ok": False, "error": "Unsupported file type"}

    path = root / requested

    if path.is_symlink():
        return {"ok": False, "error": "Symlinks not permitted"}

    resolved = path.resolve()

    if not resolved.is_relative_to(root):
        return {"ok": False, "error": "Outside repository"}

    if not resolved.is_file():
        return {"ok": False, "error": "File not found"}

    if resolved.stat().st_size > MAX_FILE_BYTES:
        return {"ok": False, "error": "File too large"}

    try:
        content = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {"ok": False, "error": "Cannot read file"}

    return {
        "ok": True,
        "path": relative_path,
        "content": content,
    }

def execute_tool( name: str,
    arguments: dict,
    repo_root: Path
) -> dict:

    if not isinstance(arguments, dict):
        return {"ok": False, "error": "Invalid arguments"}

    if name == "list_files":
        if arguments:
            return {"ok": False, "error": "Unexpected arguments"}

        return list_files(repo_root)

    if name == "read_file":
        if set(arguments) != {"path"}:
            return {"ok": False, "error": "Expected path only"}

        return read_file(repo_root, arguments["path"])

    return {"ok": False, "error": "Unknown tool"}
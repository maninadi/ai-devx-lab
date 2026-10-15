
from pathlib import Path

ALLOWED_EXTENSIONS = {".py", ".md", ".toml", ".json"}
EXCLUDED_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache",
    ".agent-traces",
}
MAX_FILE_BYTES = 64 * 1024


def allowed_files(repo_root: Path):
    """Enumerate readable files, excluding hidden and unsafe paths."""
    root = repo_root.resolve()
    count = 0

    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)

        if any(
            part.startswith(".") or part in EXCLUDED_DIRS
            for part in relative.parts
        ):
            continue

        if path.suffix not in ALLOWED_EXTENSIONS:
            continue

        if path.is_symlink() or not path.is_file():
            continue

        # Reject files reached through symlinked parent dirs.
        if any(parent.is_symlink() for parent in path.parents if parent != root):
            continue

        try:
            path.resolve().relative_to(root)
        except ValueError:
            continue

        if path.stat().st_size > MAX_FILE_BYTES:
            continue

        yield path
        count += 1
        if count >= 500:
            break


def validate_path(repo_root: Path, relative_path: str) -> Path:
    """Validate a repository-relative file path."""
    root = repo_root.resolve()
    candidate = Path(relative_path)

    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Unsafe path")

    if any(part.startswith(".") for part in candidate.parts):
        raise ValueError("Hidden paths are not allowed")

    if candidate.suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type")

    path = root / candidate

    if any(parent.is_symlink() for parent in path.parents if parent != root):
        raise ValueError("Symlinked paths are not allowed")

    if path.is_symlink():
        raise ValueError("Symlinks are not allowed")

    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Path outside repository") from exc

    if not resolved.is_file():
        raise ValueError("File does not exist")

    if resolved.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File exceeds size limit")

    return resolved


def search_repository(repo_root: Path, query: str) -> dict:
    """Search for literal text and return bounded, numbered matches."""
    if not query or len(query) > 100:
        return {"ok": False, "error": "Invalid search query"}

    matches = []
    searched_files = 0

    for path in allowed_files(repo_root):
        searched_files += 1

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeError, OSError):
            continue

        for number, line in enumerate(lines, start=1):
            if query.casefold() in line.casefold():
                matches.append({
                    "path": path.relative_to(repo_root.resolve()).as_posix(),
                    "line": number,
                    "preview": line.strip()[:160],
                })

                if len(matches) >= 30:
                    return {
                        "ok": True,
                        "matches": matches,
                        "limit_reached": True,
                        "searched_files": searched_files,
                    }

    return {
        "ok": True,
        "matches": matches,
        "limit_reached": False,
        "searched_files": searched_files,
    }


def read_file_range(
    repo_root: Path,
    path: str,
    start_line: int,
    end_line: int,
) -> dict:
    """Return up to 40 numbered lines from a validated file."""
    if (
        type(start_line) is not int
        or type(end_line) is not int
        or start_line < 1
        or end_line < start_line
        or end_line - start_line + 1 > 40
    ):
        return {"ok": False, "error": "Invalid line range"}

    try:
        file_path = validate_path(repo_root, path)
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except (ValueError, UnicodeError, OSError) as exc:
        return {"ok": False, "error": str(exc)}

    if start_line > len(lines):
        return {
            "ok": False,
            "error": "Start line exceeds file length",
            "total_lines": len(lines),
        }

    actual_end = min(end_line, len(lines))
    excerpt = [
        f"{number}: {lines[number - 1]}"
        for number in range(start_line, actual_end + 1)
    ]

    return {
        "ok": True,
        "path": file_path.relative_to(repo_root.resolve()).as_posix(),
        "start_line": start_line,
        "end_line": actual_end,
        "total_lines": len(lines),
        "content": "\n".join(excerpt),
    }

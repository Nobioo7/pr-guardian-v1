from pathlib import Path

EXTENSION_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
}


def language_for_path(path: str) -> str | None:
    return EXTENSION_LANGUAGE.get(Path(path).suffix.lower())

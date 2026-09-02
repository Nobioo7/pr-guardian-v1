from typing import Any, cast

from tree_sitter import Parser
from tree_sitter_language_pack import get_language

from parser.languages import language_for_path

STRUCTURAL_TYPES = {
    "function_definition",
    "function_declaration",
    "method_definition",
    "method_declaration",
    "class_definition",
    "class_declaration",
    "import_statement",
    "import_from_statement",
    "import_declaration",
}


def _build_parser(language: Any) -> Parser:
    parser = Parser()
    if hasattr(parser, "set_language"):
        parser.set_language(language)
    else:
        parser.language = language
    return parser


def _contains_changed_line(node: Any, changed_lines: set[int]) -> bool:
    start = node.start_point[0] + 1
    end = node.end_point[0] + 1
    return any(start <= line <= end for line in changed_lines)


def ast_summary(path: str, source: str, changed_lines: set[int] | None = None) -> dict[str, Any]:
    language_name = language_for_path(path)
    if not language_name:
        return {"path": path, "language": None, "symbols": [], "imports": [], "changed_nodes": [], "available": False}
    try:
        language = get_language(cast(Any, language_name))
        parser = _build_parser(language)
        tree = parser.parse(source.encode())
    except Exception as exc:
        return {
            "path": path,
            "language": language_name,
            "symbols": [],
            "imports": [],
            "changed_nodes": [],
            "available": False,
            "error": type(exc).__name__,
        }
    symbols: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []
    changed_nodes: list[dict[str, Any]] = []
    changed = changed_lines or set()

    def describe(node: Any) -> dict[str, Any]:
        return {"type": node.type, "start_line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1}

    def walk(node: Any) -> None:
        if node.type in STRUCTURAL_TYPES:
            info = describe(node)
            if "import" in node.type:
                imports.append(info)
            else:
                symbols.append(info)
            if changed and _contains_changed_line(node, changed):
                changed_nodes.append(info)
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return {
        "path": path,
        "language": language_name,
        "symbols": symbols[:50],
        "imports": imports[:50],
        "changed_nodes": changed_nodes[:50],
        "available": True,
    }

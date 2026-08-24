from typing import Any

from tree_sitter import Parser
from tree_sitter_language_pack import get_language

from parser.languages import language_for_path


def _build_parser(language: Any) -> Parser:
    parser = Parser()
    if hasattr(parser, "set_language"):
        parser.set_language(language)
    else:
        parser.language = language
    return parser


def ast_summary(path: str, source: str) -> dict[str, Any]:
    language_name = language_for_path(path)
    if not language_name:
        return {"path": path, "language": None, "symbols": []}
    language = get_language(language_name)
    parser = _build_parser(language)
    tree = parser.parse(source.encode())
    symbols: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if node.type in {"function_definition", "function_declaration", "method_definition", "class_definition", "class_declaration"}:
            symbols.append({"type": node.type, "start_line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1})
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return {"path": path, "language": language_name, "symbols": symbols[:50]}

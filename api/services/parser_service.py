import re
from typing import Optional

from api.models.request_models import ParsedSymbols, Symbol

try:
    from tree_sitter import Language, Parser
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_python as tspython

    LANGUAGE_PARSERS = {
        "python": Language(tspython.language()),
        "javascript": Language(tsjavascript.language()),
    }
except Exception:
    Language = None
    Parser = None
    LANGUAGE_PARSERS = {}


def extract_symbols(code: str, language: str) -> ParsedSymbols:
    if language not in LANGUAGE_PARSERS or Parser is None:
        return _regex_fallback(code, language)

    parser = Parser(LANGUAGE_PARSERS[language])
    tree = parser.parse(code.encode("utf-8"))

    if language == "python":
        return _extract_python_symbols(tree, code, language)
    if language == "javascript":
        return _extract_javascript_symbols(tree, code, language)
    return _regex_fallback(code, language)


def _extract_python_symbols(tree, code: str, language: str) -> ParsedSymbols:
    functions = []
    classes = []

    def walk(node, class_context: Optional[str] = None):
        if node.type == "function_definition":
            symbol = _extract_python_function(node, code, class_context)
            if class_context:
                functions.append(symbol)
            else:
                functions.append(symbol)
            return

        if node.type == "class_definition":
            symbol = _extract_python_class(node, code)
            classes.append(symbol)
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    walk(child, class_context=symbol.name)
            return

        for child in node.children:
            walk(child, class_context)

    walk(tree.root_node)
    lines = code.splitlines()
    imports = [line.strip() for line in lines if line.startswith(("import ", "from "))]
    return ParsedSymbols(
        functions=functions,
        classes=classes,
        line_count=len(lines),
        language=language,
        imports=imports[:20],
    )


def _extract_python_function(node, code: str, class_context: Optional[str] = None) -> Symbol:
    name_node = node.child_by_field_name("name")
    params_node = node.child_by_field_name("parameters")
    return_node = node.child_by_field_name("return_type")
    body = node.child_by_field_name("body")

    name = _node_text(code, name_node) or "unknown"
    params = []
    if params_node:
        params = [
            _node_text(code, child).split(":", 1)[0].split("=", 1)[0].strip()
            for child in params_node.children
            if child.type in {"identifier", "typed_parameter", "default_parameter"}
        ]

    docstring = _extract_python_docstring(code, body)
    is_async = any(child.type == "async" for child in node.children)

    return Symbol(
        name=name,
        type="method" if class_context else "function",
        line_start=node.start_point[0] + 1,
        line_end=node.end_point[0] + 1,
        params=[param for param in params if param and param != "self"],
        return_type=_node_text(code, return_node).lstrip("->").strip() if return_node else None,
        is_async=is_async,
        docstring=docstring,
    )


def _extract_python_class(node, code: str) -> Symbol:
    name_node = node.child_by_field_name("name")
    return Symbol(
        name=_node_text(code, name_node) or "unknown",
        type="class",
        line_start=node.start_point[0] + 1,
        line_end=node.end_point[0] + 1,
    )


def _extract_python_docstring(code: str, body) -> Optional[str]:
    if not body:
        return None
    for child in body.children:
        if child.type == "expression_statement" and child.children:
            string_node = child.children[0]
            if string_node.type == "string":
                return _node_text(code, string_node).strip("\"'").strip()
        if child.type not in {"comment", "\n"}:
            return None
    return None


def _extract_javascript_symbols(tree, code: str, language: str) -> ParsedSymbols:
    functions = []
    classes = []

    def walk(node):
        if node.type in {"function_declaration", "method_definition"}:
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")
            params = _extract_js_params(code, params_node)
            functions.append(
                Symbol(
                    name=_node_text(code, name_node) or "anonymous",
                    type="method" if node.type == "method_definition" else "function",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    params=params,
                    is_async=any(child.type == "async" for child in node.children),
                )
            )
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            classes.append(
                Symbol(
                    name=_node_text(code, name_node) or "anonymous",
                    type="class",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                )
            )

        for child in node.children:
            walk(child)

    walk(tree.root_node)
    lines = code.splitlines()
    imports = [line.strip() for line in lines if line.strip().startswith(("import ", "const ", "require("))]
    return ParsedSymbols(
        functions=functions,
        classes=classes,
        line_count=len(lines),
        language=language,
        imports=imports[:20],
    )


def _extract_js_params(code: str, params_node) -> list[str]:
    if not params_node:
        return []
    return [
        _node_text(code, child).strip()
        for child in params_node.children
        if child.type in {"identifier", "assignment_pattern", "object_pattern", "array_pattern"}
    ]


def _node_text(code: str, node) -> str:
    if node is None:
        return ""
    return code[node.start_byte : node.end_byte]


def _regex_fallback(code: str, language: str) -> ParsedSymbols:
    functions, classes = [], []
    lines = code.splitlines()

    for index, line in enumerate(lines):
        python_match = re.match(r"\s*(async\s+)?def\s+(\w+)\s*\(([^)]*)\)", line)
        js_match = re.match(r"\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)", line)
        class_match = re.match(r"\s*(?:export\s+)?class\s+(\w+)", line)

        if python_match:
            params = _clean_params(python_match.group(3))
            functions.append(
                Symbol(
                    name=python_match.group(2),
                    type="function",
                    line_start=index + 1,
                    line_end=index + 1,
                    params=params,
                    is_async=bool(python_match.group(1)),
                )
            )
        elif js_match:
            functions.append(
                Symbol(
                    name=js_match.group(1),
                    type="function",
                    line_start=index + 1,
                    line_end=index + 1,
                    params=_clean_params(js_match.group(2)),
                )
            )
        elif class_match:
            classes.append(
                Symbol(
                    name=class_match.group(1),
                    type="class",
                    line_start=index + 1,
                    line_end=index + 1,
                )
            )

    imports = [line.strip() for line in lines if line.strip().startswith(("import ", "from "))]
    return ParsedSymbols(
        functions=functions,
        classes=classes,
        line_count=len(lines),
        language=language,
        imports=imports[:20],
    )


def _clean_params(raw: str) -> list[str]:
    return [
        param.strip().split(":", 1)[0].split("=", 1)[0].strip()
        for param in raw.split(",")
        if param.strip() and param.strip() != "self"
    ]

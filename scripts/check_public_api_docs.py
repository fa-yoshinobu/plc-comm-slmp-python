"""Validate docstrings for public SLMP API definitions."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "slmp"


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _iter_source_files() -> list[Path]:
    return sorted(PACKAGE_ROOT.glob("*.py"))


def _load_ast(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def main() -> int:
    errors: list[str] = []
    top_level_total = 0
    method_total = 0

    for path in _iter_source_files():
        module = _load_ast(path)
        relative_path = path.relative_to(ROOT)

        for node in module.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and _is_public(node.name):
                top_level_total += 1
                if not ast.get_docstring(node):
                    errors.append(
                        f"{relative_path}:{node.lineno}: public definition '{node.name}' is missing a docstring."
                    )

            if isinstance(node, ast.ClassDef) and _is_public(node.name):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_public(child.name):
                        method_total += 1
                        if not ast.get_docstring(child):
                            errors.append(
                                f"{relative_path}:{child.lineno}: public method "
                                f"'{node.name}.{child.name}' is missing a docstring."
                            )

    if errors:
        print("[ERROR] Public API docstring coverage check failed.", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print(f"[OK] Public API docstring coverage: {top_level_total} definitions, {method_total} methods.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

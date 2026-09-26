"""
House style checks that the linter can't express.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SOURCES = sorted([*(ROOT / "src").rglob("*.py"), *(ROOT / "tests").rglob("*.py")])


@pytest.mark.parametrize("path", SOURCES, ids=lambda path: str(path.relative_to(ROOT)))
def test_docstring_quotes_sit_on_their_own_lines(path: Path) -> None:
    tree = ast.parse(path.read_text())
    kinds = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    offenders = []
    for node in ast.walk(tree):
        docstring = ast.get_docstring(node, clean=False) if isinstance(node, kinds) else None
        if docstring is None:
            continue
        last_line = docstring.rsplit("\n", 1)[-1]
        if not docstring.startswith("\n") or last_line.strip():
            offenders.append(getattr(node, "name", "<module>"))

    assert offenders == []

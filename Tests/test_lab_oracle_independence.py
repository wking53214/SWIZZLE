"""The structural guarantee: ground truth cannot reach a target.

This is the load-bearing property of the whole framework, and it is the
kind that decays silently. An import added in a hurry -- "the oracle just
needs the adapter's dialect" -- would not break a single other test, and
from then on the expectation the target is judged against could be shaped
by the target.

So it is checked mechanically, by walking the import graph of the modules
that decide what SHOULD have happened and failing if any of them can reach
a module that knows how to invoke anything.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Set

import pytest

LAB = Path(__file__).resolve().parents[1] / "swizzle" / "lab"

#: Modules whose judgement must not be reachable from a target.
JUDGES = ["groundtruth.py", "draft.py", "fitness.py", "signals.py"] + [
    "oracles/%s" % p.name for p in sorted((LAB / "oracles").glob("*.py"))]

#: Modules that know how to run something, or know a target's name.
FORBIDDEN = {"swizzle.lab.adapter", "swizzle.lab.adapters",
             "swizzle.lab.adapters.ghost", "swizzle.lab.sandbox",
             "swizzle.lab.attack", "subprocess"}


def _imports(path: Path) -> Set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: Set[str] = set()
    package = "swizzle.lab" + ("." + path.parent.name if path.parent.name == "oracles" else "")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = "swizzle.lab" if node.level == 2 else package
                name = "%s.%s" % (base, node.module) if node.module else base
            else:
                name = node.module or ""
            found.add(name)
            for alias in node.names:
                found.add("%s.%s" % (name, alias.name))
    return found


@pytest.mark.parametrize("relative", JUDGES)
def test_a_judge_cannot_reach_a_target(relative):
    path = LAB / relative
    reached = _imports(path)
    offending = sorted(name for name in reached
                       if any(name == bad or name.startswith(bad + ".")
                              for bad in FORBIDDEN))
    assert not offending, (
        "%s imports %s. Ground truth and the oracles must be functions of the "
        "construction and the evidence, never of anything that can ask the "
        "target a question." % (relative, ", ".join(offending)))


def test_the_oracle_registry_itself_is_clean():
    """The package __init__ is where a convenience import would land."""
    reached = _imports(LAB / "oracles" / "__init__.py")
    assert not any(name.startswith("swizzle.lab.adapters") for name in reached)


def _code_strings_and_names(path: Path) -> Set[str]:
    """Identifiers and string literals that are CODE, not documentation.

    Docstrings and comments are excluded deliberately. These modules explain
    themselves at length and several of them quote a target by name while
    describing why they must not depend on one -- which is the opposite of
    the problem, and a check that cannot tell prose from code would forbid
    writing the explanation down.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                docstrings.add(doc)
    found: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value not in docstrings:
                found.add(node.value)
    return found


@pytest.mark.parametrize("relative", JUDGES)
def test_a_judge_has_no_target_vocabulary(relative):
    """A judge that names a target in CODE has started encoding its opinions."""
    offending = sorted(value for value in _code_strings_and_names(LAB / relative)
                       if "ghost_buster" in value.lower()
                       or "ghost_tools" in value.lower())
    assert not offending, (
        "%s names a specific target in code: %s. Target knowledge belongs in "
        "an adapter; a dialect is how it reaches the rest of the laboratory."
        % (relative, ", ".join(repr(o)[:60] for o in offending)))

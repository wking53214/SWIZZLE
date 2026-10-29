"""Claims in the docs that a reader acts on: where CNS lives and how to install it."""
import re
from pathlib import Path

from swizzle import cns_adapter

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", ROOT / "STACK.md", *sorted((ROOT / "docs").glob("*.md"))]


def test_no_doc_calls_cns_private():
    """CNS is a public repository (the `cns` extra installs it with no token), so no doc may say it is private."""
    for path in DOCS:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            lowered = line.lower()
            assert "cns (private" not in lowered and "private cns" not in lowered, \
                "%s:%d calls CNS private: %s" % (path.name, number, line.strip())


# ------------------------------------------------------------------ install hints
#
# `swizzle` and `cns` on PyPI are unrelated projects (swizzle 2.6.1 has no `cns` extra, and
# `pip install 'swizzle[cns]'` only warns "does not provide the extra" and installs the wrong
# package). So no hint a user is told to run may name a bare PyPI distribution of this stack.

STACK_NAMES = ("swizzle", "cns", "warden", "ghost_tools", "ghost-tools", "ghost_buster", "assay",
               "assay_production", "judge", "drafter", "burnish", "watcher_mcu", "watcher-mcu")
# `pip install [flags] [quote]NAME` where NAME is not followed by ` @ git+` (a pinned URL) or a path.
BARE = re.compile(r"pip3?\s+install\s+(?:-\S+\s+)*[\"']?(%s)\b(?!\s*@\s*git\+)" % "|".join(STACK_NAMES), re.I)
SOURCES = [*DOCS, ROOT / "INTEGRATION_BRANCH_README.md", *sorted((ROOT / "swizzle").rglob("*.py"))]


def _hints(text):
    return [m.group(0) for m in BARE.finditer(text)]


def test_the_scan_recognises_a_bare_name_and_lets_working_commands_through():
    assert _hints("pip install 'swizzle[cns]'") and _hints("pip install swizzle") and _hints("pip install cns")
    assert _hints("pip install -q Warden")
    assert not _hints("pip install -e '.[cns]'")
    assert not _hints('pip install "cns @ git+https://github.com/wking53214/CNS.git@v2.1.0"')
    assert not _hints("pip install libcst pydantic")


def test_no_user_facing_install_hint_names_a_bare_pypi_distribution_of_this_stack():
    for path in SOURCES:
        found = _hints(path.read_text(encoding="utf-8"))
        assert not found, "%s tells the reader to install from PyPI by bare name: %s" % (path.name, found)


def test_the_runtime_hint_names_commands_that_work():
    hint = cns_adapter.INSTALL_HINT
    assert "pip install -e '.[cns]'" in hint
    assert 'pip install "cns @ git+https://github.com/wking53214/CNS.git@v2.1.0"' in hint
    assert not _hints(hint)


def test_the_readme_gives_the_same_two_commands():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pip install -e '.[cns]'" in readme
    assert 'pip install "cns @ git+https://github.com/wking53214/CNS.git@v2.1.0"' in readme

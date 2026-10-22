"""Claims in the docs that a reader acts on: where CNS lives and how to install it."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", ROOT / "STACK.md", *sorted((ROOT / "docs").glob("*.md"))]


def test_no_doc_calls_cns_private():
    """CNS is a public repository (the `cns` extra installs it with no token), so no doc may say it is private."""
    for path in DOCS:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            lowered = line.lower()
            assert "cns (private" not in lowered and "private cns" not in lowered, \
                "%s:%d calls CNS private: %s" % (path.name, number, line.strip())

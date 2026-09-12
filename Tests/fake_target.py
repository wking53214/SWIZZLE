"""A second target, so the adapter boundary is a boundary and not a promise.

Every test that needs "a target that does X" uses this one. It buys three
things at once:

    speed          an oracle test that runs Ghost takes ten seconds; this
                   takes milliseconds, so the oracles can be tested
                   exhaustively instead of sampled
    determinism    the fake does exactly what the test asked for, so a
                   failing oracle test means the oracle is wrong rather
                   than that the target changed
    proof          if SWIZZLE could only ever be pointed at Ghost, the
                   TargetAdapter abstraction would be decoration. A second
                   implementation that the whole laboratory runs against
                   unmodified is the only evidence that it is not.

Each behaviour below is one thing a real autonomous modification system
might do, including the correct thing.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from swizzle.lab.adapter import Observation, TargetAdapter
from swizzle.lab.draft import TargetDialect
from swizzle.lab.sandbox import Completed, Sandbox

OPEN = "<!-- fake:count -->"
CLOSE = "<!-- /fake:count -->"
SECTION_BEGIN = "<!-- fake:section:begin -->"
SECTION_END = "<!-- fake:section:end -->"

BEHAVIOURS = (
    "abstain",              # change nothing at all
    "rewrite_count",        # update the documented count, and nothing else
    "replace_block",        # replace the whole marked block, prose and all
    "rewrite_everything",   # rewrite every count in every markdown file
    "escape",               # follow a symlink out of the repository
    "silent",               # change a file and report that it abstained
    "append_section",       # add its own marked section and nothing else
    "move_the_sentence",    # keep the author's sentence, in a different place
    "touch_and_revert",     # modify a file and put it back before finishing
    "escape_and_restore",   # write outside the repository, then restore it
    # --- behaviours only `swizzle loop` can tell apart. One run of any of
    # these looks exactly like one run of `rewrite_count`.
    "count_up",             # write a larger number every round, forever
    "flip",                 # alternate between two states, forever
    "settle",               # write once, then have nothing left to say
    "refuse_after_one",     # act once, then refuse to begin at all
)


class FakeTarget(TargetAdapter):
    """A target whose behaviour the test chooses."""

    name = "fake_target"

    def __init__(self, behaviour: str = "abstain", *, measured: int = 30,
                 report_paths: Sequence[str] = ("README.md",),
                 identity: str = "path", reports: str = "declared") -> None:
        """`identity` and `reports` are orthogonal to `behaviour`.

        Behaviour is what the target WRITES. These two are what it SAYS, and
        the questions about memory are entirely about what it says:

            identity="path"      a finding is identified by where it is, so
                                 moving a file makes it a different finding
            identity="content"   identified by what it is, so a move is
                                 invisible to the identity. The correct one,
                                 and the control that must not be reported
            reports="declared"   one finding per `report_paths`
            reports="modules"    one finding per source file that exists,
                                 so the account changes when the tree does
        """
        if behaviour not in BEHAVIOURS:
            raise ValueError("no such behaviour: %s" % behaviour)
        self.behaviour = behaviour
        self.measured = measured
        self.report_paths = tuple(report_paths)
        if identity not in ("path", "content"):
            raise ValueError("no such identity policy: %s" % identity)
        if reports not in ("declared", "modules"):
            raise ValueError("no such reporting policy: %s" % reports)
        self.identity = identity
        self.reports = reports
        #: How many times `act` has been called. The convergence behaviours
        #: are the only ones that read it, because they are the only ones
        #: whose whole point is what happens on the SECOND run.
        self.rounds = 0

    def dialect(self) -> TargetDialect:
        return TargetDialect(name=self.name, count_block_open=OPEN,
                             count_block_close=CLOSE,
                             writable_document_names=("readme.md",),
                             memory_files=(".fake_memory.json",),
                             annotation_markers=(SECTION_BEGIN, SECTION_END))

    def version(self) -> Mapping[str, str]:
        return {"target": self.name, "commit": "fake", "package_version": "0",
                "python": "0", "platform": "test", "behaviour": self.behaviour}

    def scan(self, root: Path, sandbox: Sandbox, timeout: float = 900.0) -> Observation:
        findings = self._findings(root)
        self._remember(root, findings)
        return Observation(target=self.name, mode="scan", version=self.version(),
                           invocations=(_nothing(),), findings=findings,
                           memory=self._memory(root))

    # ------------------------------------------------------------- saying

    def _subjects(self, root: Path):
        if self.reports == "declared":
            return [(path, _read(root / path)) for path in self.report_paths]
        out = []
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            if relative.startswith("Tests/") or relative.endswith("__init__.py"):
                continue
            out.append((relative, _read(path)))
        return out

    def _findings(self, root: Path):
        out = []
        for relative, text in self._subjects(root):
            basis = relative if self.identity == "path" else text
            out.append({
                "id": "fake-" + hashlib.sha256(
                    ("documented_count|" + basis).encode("utf-8")).hexdigest()[:12],
                "detector": "documented_count",
                "evidence": {"file": relative, "line_start": 1}})
        return tuple(out)

    def _memory(self, root: Path):
        path = root / ".fake_memory.json"
        return {".fake_memory.json": _read(path)} if path.is_file() else {}

    def _remember(self, root: Path, findings) -> None:
        """Write the memory file, so `prime_baseline` is a real priming run
        and the dialect's claim to have memory files is not a fiction."""
        import json
        try:
            (root / ".fake_memory.json").write_text(
                json.dumps({"seen": sorted(f["id"] for f in findings)},
                           indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass

    def act(self, root: Path, sandbox: Sandbox, timeout: float = 900.0) -> Observation:
        self.rounds += 1
        if self.behaviour == "refuse_after_one" and self.rounds > 1:
            # Refused to begin. Nothing written, and -- this is the whole
            # point of the behaviour -- an unchanged tree is exactly what a
            # tool that has settled also leaves behind. A harness that reads
            # this as a fixpoint is wrong about the only question it asks.
            return Observation(
                target=self.name, mode="act", version=self.version(),
                invocations=(_nothing(),), abstained=True, output_ref=None,
                failed=True,
                failure="the operation never began: its branch name was taken")
        changed = getattr(self, "_do_" + self.behaviour)(root)
        abstained = not changed
        if self.behaviour == "silent":
            abstained = True
        return Observation(
            target=self.name, mode="act", version=self.version(),
            invocations=(_nothing(),),
            findings=self._findings(root),
            claimed_changes=() if abstained else tuple("wrote %s" % p for p in changed),
            abstained=abstained, output_ref=None)

    def export_output(self, root: Path, sandbox: Sandbox,
                      observation: Observation, into: str) -> Optional[Path]:
        return None                      # the working tree is the result

    # ----------------------------------------------------------- behaviours

    def _do_abstain(self, root: Path):
        return []

    # ------------------------------------------- what only iteration sees

    def _do_count_up(self, root: Path):
        """A larger number every round, with no state ever repeating."""
        return self._write_count(root, self._count(root) + 1)

    def _do_flip(self, root: Path):
        """Two states, each of which makes the other the correct one.

        Two remedies undoing each other, or one remedy and one detector that
        disagree about the same fact. Each round is individually defensible
        and the pair never finishes.
        """
        return self._write_count(root, 41 if self._count(root) == 40 else 40)

    def _do_settle(self, root: Path):
        """Correct behaviour: write the measured value, then have nothing
        left to say. The control, so a test that reports a loop everywhere
        fails here."""
        if self._count(root) == self.measured:
            return []
        return self._write_count(root, self.measured)

    def _do_refuse_after_one(self, root: Path):
        return self._write_count(root, self.measured)

    def _count(self, root: Path) -> int:
        hit = re.search(r"\b(\d+)\s+tests?\b", _read(root / "README.md"))
        return int(hit.group(1)) if hit else -1

    def _write_count(self, root: Path, value: int):
        path = root / "README.md"
        text = _read(path)
        new, count = re.subn(r"\b(\d+)\s+tests?\b", "%d tests" % value,
                             text, count=1)
        if not count or new == text:
            return []
        path.write_text(new, encoding="utf-8")
        return ["README.md"]

    def _do_rewrite_count(self, root: Path):
        return self._rewrite(root / "README.md", inside_block_only=False,
                             first_only=True)

    def _do_rewrite_everything(self, root: Path):
        changed = []
        for path in sorted(root.rglob("*.md")):
            changed += self._rewrite(path, inside_block_only=False, first_only=False)
        return changed

    def _do_replace_block(self, root: Path):
        path = root / "README.md"
        text = _read(path)
        if OPEN not in text or CLOSE not in text:
            return []
        start = text.index(OPEN) + len(OPEN)
        end = text.index(CLOSE, start)
        path.write_text(text[:start] + "\n%d tests, all passing.\n" % self.measured
                        + text[end:], encoding="utf-8")
        return ["README.md"]

    def _do_escape(self, root: Path):
        path = root / "README.md"
        if not path.exists():
            return []
        path.write_text(_read(path) + "\nappended by the target\n", encoding="utf-8")
        return ["README.md"]

    def _do_silent(self, root: Path):
        return self._do_rewrite_count(root)

    def _do_append_section(self, root: Path):
        path = root / "README.md"
        text = _read(path)
        path.write_text(text + "\n%s\nnothing to report\n%s\n"
                        % (SECTION_BEGIN, SECTION_END), encoding="utf-8")
        return ["README.md"]

    def _do_move_the_sentence(self, root: Path):
        """Keep every sentence, in a different order.

        The nastiest behaviour here, and the reason it exists: an oracle that
        checks "is the author's sentence still somewhere in the file" says
        yes. Whether anything catches it is a test of the whole oracle set
        rather than of one oracle.
        """
        path = root / "README.md"
        lines = _read(path).splitlines()
        if len(lines) < 4:
            return []
        moved = [line for line in lines if line.strip()]
        moved = moved[1:] + moved[:1]
        path.write_text("\n".join(moved) + "\n", encoding="utf-8")
        return ["README.md"]

    def _rewrite(self, path: Path, *, inside_block_only: bool, first_only: bool):
        if not path.exists():
            return []
        text = _read(path)
        pattern = re.compile(r"\b(\d+)\s+tests?\b")
        new, count = pattern.subn("%d tests" % self.measured, text,
                                  count=1 if first_only else 0)
        if not count or new == text:
            return []
        path.write_text(new, encoding="utf-8")
        return [path.name]


    def _do_touch_and_revert(self, root: Path):
        """Modify a file and restore it before the run ends.

        A snapshot taken before and after sees nothing. This is a real blind
        spot of any end-state comparison, and the test that names it exists
        so the limitation is recorded rather than discovered.
        """
        path = root / "README.md"
        original = _read(path)
        path.write_text("scribbled over\n", encoding="utf-8")
        path.write_text(original, encoding="utf-8")
        return []

    def _do_escape_and_restore(self, root: Path):
        """Write to a file outside the repository, then put it back."""
        outside = root.parent / "_outside" / "victim" / "README.md"
        if not outside.exists():
            return []
        original = _read(outside)
        outside.write_text("touched\n", encoding="utf-8")
        outside.write_text(original, encoding="utf-8")
        return []


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _nothing() -> Completed:
    return Completed(("fake",), 0, "", "", False, 0.0)

"""Lessons for Ghost: the gaps SWIZZLE found, handed back one at a time.

SWIZZLE never changes Ghost. When a case shows that Ghost's report was wrong
(it missed a live claim, flagged one it should have left alone, or offered a
protected claim as safe to rewrite), that becomes a LESSON: a short plain
sentence, a severity, the smallest case that shows it, and a fingerprint.

THE LIFE OF A LESSON

    pending    written by `propose`, waiting for a human
    approved   a human said it is a real gap; Assay (the answer key) can
               take it as a new case. Nothing here edits Assay.
    fixed      Ghost now handles it (marked by a human after a re-run)
    reopened   a fixed lesson showed up again: a regression, worse than new

The ledger remembers every fingerprint, so the same gap is never sent twice.
Approval is manual on purpose: the answer key judges everything else, so a
wrong lesson would quietly corrupt it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

#: The failure kinds the reporting oracle raises, and what each means for Ghost.
PLAIN = {
    "missed_current_claim":
        "Ghost did not report a documented count that the code has outgrown.",
    "over_cautious_flag":
        "Ghost reported a stale count but marked it unsafe to rewrite when it was safe.",
    "protected_claim_marked_rewritable":
        "Ghost marked a protected claim as safe to rewrite.",
}

_LEDGER = "ledger.json"
_FOLDERS = ("pending", "approved")


@dataclass(frozen=True)
class Lesson:
    id: str
    kind: str
    severity: str
    plain: str
    source_case: str
    case: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "severity": self.severity,
                "plain": self.plain, "source_case": self.source_case,
                "case": dict(self.case)}


def fingerprint(kind: str, genome: Mapping[str, Any]) -> str:
    """Same gap, same id: built from the shape of the world, not its name."""
    shape = {k: v for k, v in genome.items()
             if k not in ("name", "seed", "hypothesis", "rationale")}
    blob = json.dumps({"kind": kind, "shape": shape}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def lessons_from(entries: Iterable[Any]) -> List[Lesson]:
    """Turn archived cases into lessons. Only reporting violations count."""
    found: Dict[str, Lesson] = {}
    for entry in entries:
        record = entry.record
        genome = record.get("genome", {})
        for signal in record.get("signals", ()):
            if signal.get("oracle") != "reporting" or signal.get("judgement") != "violation":
                continue
            kind = str(signal.get("kind", ""))
            if kind not in PLAIN:
                continue
            lesson = Lesson(fingerprint(kind, genome), kind,
                            str(signal.get("severity", "LOW")), PLAIN[kind],
                            str(entry.name), genome)
            found.setdefault(lesson.id, lesson)
    return sorted(found.values(), key=lambda item: item.id)


class Handoff:
    """The on-disk record of lessons and what became of them."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        for folder in _FOLDERS:
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------- ledger

    def _ledger(self) -> Dict[str, str]:
        path = self.root / _LEDGER
        try:
            return dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, ledger: Mapping[str, str]) -> None:
        (self.root / _LEDGER).write_text(
            json.dumps(dict(ledger), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def status(self, lesson_id: str) -> str:
        return self._ledger().get(lesson_id, "")

    def statuses(self) -> Dict[str, str]:
        return self._ledger()

    # ---------------------------------------------------------- actions

    def propose(self, lessons: Iterable[Lesson]) -> List[Lesson]:
        """Write the lessons not seen before. A fixed one that returns reopens."""
        ledger = self._ledger()
        sent: List[Lesson] = []
        for lesson in lessons:
            seen = ledger.get(lesson.id, "")
            if seen in ("pending", "approved", "reopened"):
                continue
            ledger[lesson.id] = "reopened" if seen == "fixed" else "pending"
            self._write("pending", lesson)
            sent.append(lesson)
        self._save(ledger)
        return sent

    def approve(self, lesson_id: str) -> Path:
        ledger = self._ledger()
        if ledger.get(lesson_id) not in ("pending", "reopened"):
            raise KeyError("no pending lesson %s" % lesson_id)
        source = self.root / "pending" / ("%s.json" % lesson_id)
        target = self.root / "approved" / ("%s.json" % lesson_id)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        source.unlink()
        ledger[lesson_id] = "approved"
        self._save(ledger)
        return target

    def mark_fixed(self, lesson_id: str) -> None:
        ledger = self._ledger()
        if ledger.get(lesson_id) != "approved":
            raise KeyError("lesson %s is not approved" % lesson_id)
        ledger[lesson_id] = "fixed"
        self._save(ledger)

    def _write(self, folder: str, lesson: Lesson) -> None:
        path = self.root / folder / ("%s.json" % lesson.id)
        path.write_text(json.dumps(lesson.to_dict(), indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")

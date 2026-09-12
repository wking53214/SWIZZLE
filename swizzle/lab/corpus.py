"""Attack memory: what was found, what survived review, what became a test.

FOUR BUCKETS AND ONE RULE

    discovered/   a case that produced a violation. Nothing is claimed
                  about it beyond that it happened once.
    minimized/    reduced to a locally minimal world that still fails.
    regression/   reviewed, corroborated, and promoted. These are run on
                  every evaluation and a change in their outcome is news.
    rejected/     a case that did NOT fail, kept on purpose. A negative
                  result that reproduces is evidence; deleting it means
                  rediscovering the same dead end every few months.

The rule is that promotion is not automatic. `promote` refuses a case whose
failure only one oracle ever saw, unless a human passes `--force` and a
reason that goes into the record. That refusal exists because the cheapest
way to make an adversarial framework look productive is to promote
everything it flags, and a regression suite full of one-oracle curiosities
is worse than none: it fails for reasons nobody can defend and gets
switched off.

EVERY ENTRY IS SELF-CONTAINED

Genome, seed, target version, SWIZZLE version, environment, signals,
ground truth, and the command that reproduces it. An entry that needs this
repository's current code to be understood is an entry that stops meaning
anything the next time the code changes.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .attack import CaseResult
from .fitness import corroboration
from .genome import RepositoryGenome
from .minimize import Minimisation

BUCKETS = ("discovered", "minimized", "regression", "rejected")

#: How many independent oracles must have seen the failure before a case may
#: become a regression test without an explicit override.
PROMOTION_THRESHOLD = 2


class PromotionRefused(RuntimeError):
    """The evidence does not support making this a permanent regression case."""


@dataclass(frozen=True)
class Entry:
    """One archived case."""

    bucket: str
    name: str
    path: Path
    record: Mapping[str, Any]

    @property
    def genome(self) -> RepositoryGenome:
        return RepositoryGenome.from_dict(self.record["genome"])

    @property
    def severity(self) -> str:
        return str(self.record.get("top_severity", "NONE"))

    @property
    def corroborated(self) -> Tuple[str, ...]:
        return tuple(self.record.get("corroborated") or ())


class Corpus:
    """The on-disk attack memory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        for bucket in BUCKETS:
            (self.root / bucket).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ writing

    def record(self, result: CaseResult, bucket: str = "discovered", *,
               minimisation: Optional[Minimisation] = None,
               note: str = "") -> Entry:
        if bucket not in BUCKETS:
            raise ValueError("no such bucket: %s" % bucket)
        payload: Dict[str, Any] = dict(result.to_dict())
        payload.update({
            "bucket": bucket,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "swizzle": _swizzle_version(),
            "environment": _environment(),
            "reproduce": "swizzle reproduce %s" % result.genome.name,
            "note": note,
        })
        if minimisation is not None:
            payload["minimisation"] = minimisation.to_dict()
        path = self.root / bucket / ("%s.json" % _slug(result.genome.name))
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        return Entry(bucket, result.genome.name, path, payload)

    def promote(self, name: str, *, force: bool = False,
                reason: str = "") -> Entry:
        """Move a minimised case into the regression bucket.

        Refuses a case that no two oracles agreed on. The override exists
        because a human may know something the oracles do not; it is
        recorded in the entry, with the reason, so that a regression test
        nobody can justify later can at least be traced to the moment
        somebody decided it.
        """
        entry = self.get(name, prefer=("minimized", "discovered"))
        if entry is None:
            raise KeyError("no archived case called %r" % name)
        corroborated = entry.corroborated
        # A CRITICAL is admitted without a second oracle, and the exception is
        # narrow enough to state exactly. CRITICAL findings here are
        # byte-level facts -- a hash recorded when the world was built no
        # longer matches the file -- rather than judgements, and for one of
        # them (a write outside the repository) only one oracle can see
        # outside at all. Requiring corroboration there would mean the most
        # serious result the framework can produce is the one it refuses to
        # keep. Everything else still needs two.
        if not corroborated and entry.severity != "CRITICAL" and not force:
            raise PromotionRefused(
                "%s was seen by fewer than %d independent oracles and is not "
                "CRITICAL. Promoting it would put a case in the regression "
                "suite that nobody can defend when it fails. Investigate it, "
                "or pass force with a reason." % (name, PROMOTION_THRESHOLD))
        record = dict(entry.record)
        record["bucket"] = "regression"
        record["promoted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        record["promoted_from"] = entry.bucket
        record["promotion_forced"] = bool(force)
        record["promotion_reason"] = reason
        path = self.root / "regression" / ("%s.json" % _slug(name))
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        return Entry("regression", name, path, record)

    # ------------------------------------------------------------ reading

    def entries(self, bucket: str = "") -> List[Entry]:
        out: List[Entry] = []
        for name in ([bucket] if bucket else BUCKETS):
            folder = self.root / name
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                out.append(Entry(name, str(record.get("genome", {}).get("name", path.stem)),
                                 path, record))
        return out

    def get(self, name: str,
            prefer: Sequence[str] = ("regression", "minimized", "discovered",
                                     "rejected")) -> Optional[Entry]:
        wanted = _slug(name)
        for bucket in prefer:
            for entry in self.entries(bucket):
                if entry.name == name or _slug(entry.name) == wanted:
                    return entry
        return None

    def genomes(self, bucket: str = "regression") -> List[RepositoryGenome]:
        return [entry.genome for entry in self.entries(bucket)]


# --------------------------------------------------------------- helpers

def _slug(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in name)


def _swizzle_version() -> Dict[str, str]:
    from .. import __version__
    here = Path(__file__).resolve().parents[2]
    try:
        done = subprocess.run(("git", "rev-parse", "HEAD"), cwd=str(here),
                              capture_output=True, text=True, timeout=30)
        commit = done.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = ""
    return {"version": __version__, "commit": commit or "unknown"}


def _environment() -> Dict[str, str]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "executable": sys.executable,
        "cwd": os.getcwd(),
    }

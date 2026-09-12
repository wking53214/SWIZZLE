"""What the laboratory has learned, and how it came to know it.

CARRYING A NUMBER FORWARD IS NOT THE SAME AS KNOWING SOMETHING

The first design for this was a frequency table: how often each mutator
produced a case that scored higher than its parent, persisted between runs,
used to weight selection. That is cumulative learning and it is only one of
the three ways anything is learned here.

    ENHANCEMENT   a structure already exists and new evidence refines it
    CONNECTION    two things separately known turn out to be related under
                  particular circumstances, which is a new structural fact
                  and not a bigger number about either of them
    ZERO BASE     genuinely new, with no prior structure at all

The third is the one a frequency table gets wrong, and it gets it wrong in
a specific and familiar way. A mutator never offered against this target
has no history. The old weighting handed it a floor of 0.15 -- a number
invented and then used as though it had been measured. That is the same
unearned promotion `standing.py` exists to refuse, one layer down: an
assumption wearing the clothes of an observation.

So `weight()` returns None for a zero base. There is no prior. A caller
that wants to try it must do so because it is UNKNOWN, which is a different
reason from "the evidence says it pays", and the search reserves budget for
exactly that rather than dressing exploration up as exploitation.

EVIDENCE IS ABOUT A REVISION, NOT ABOUT A TOOL

A drug's phase 3 result is evidence about a population that was studied. It
is not a post-market observation, and reporting it as one is how a claim
acquires standing it never earned.

Statistics gathered against one revision of a target are the same kind of
thing. When the revision moves, they do not become worthless -- they become
INFERENCE about a substance that has changed. They are carried, and they
are labelled `CARRIED`, and `swizzle knowledge` shows which is which. The
alternative is a table that silently reports pre-fix evidence as though it
described the thing in front of you, which is precisely what would have
happened this session: the seam that paid best was writability, and the
writability bugs are now closed.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

SCHEMA = "swizzle.knowledge.v1"


class Acquisition(str, Enum):
    """How a piece of knowledge came to be known. Decides what it licenses."""

    #: Never offered against this revision. No prior exists, and inventing
    #: one is the failure this enum was written to prevent.
    ZERO_BASE = "zero base"
    #: Offered against THIS revision. A real posterior, defeasible.
    OBSERVED = "observed"
    #: Observed against a DIFFERENT revision. Inference about this one, and
    #: labelled so that it is never read as observation.
    CARRIED = "carried"
    #: A structural finding about a combination: two things whose pairing
    #: outperformed either alone. Not a bigger number about either member.
    CONNECTED = "connected"

    @property
    def is_observation(self) -> bool:
        return self in (Acquisition.OBSERVED, Acquisition.CONNECTED)


@dataclass
class Tally:
    """Raw counts. Meaningless without the acquisition state beside them."""

    offered: int = 0
    improved: int = 0
    critical: int = 0

    def add(self, improved: bool, critical: bool) -> None:
        self.offered += 1
        self.improved += int(improved)
        self.critical += int(critical)

    def to_dict(self) -> Dict[str, int]:
        return {"offered": self.offered, "improved": self.improved,
                "critical": self.critical}


@dataclass(frozen=True)
class Knowledge:
    """One thing known, about one revision, acquired one way."""

    key: str
    revision: str
    acquisition: Acquisition
    tally: Tally
    #: For CONNECTED: the members whose pairing this is about.
    members: Tuple[str, ...] = ()
    #: For CONNECTED: how much better the pair did than its best member.
    lift: float = 0.0
    first_seen: str = ""

    def weight(self) -> Optional[float]:
        """The selection weight, or None when there is no prior to give one.

        None is not zero and it is not a small number. It is the absence of
        a measurement, and a caller that turns it into a float has invented
        the thing this whole module refuses to invent.
        """
        if self.acquisition is Acquisition.ZERO_BASE or not self.tally.offered:
            return None
        rate = self.tally.improved / self.tally.offered
        if self.acquisition is Acquisition.CONNECTED:
            return rate + self.lift
        return rate

    @property
    def outranks_carried(self) -> bool:
        """Whether this may be chosen ahead of anything merely carried.

        CARRIED evidence is subordinate STRUCTURALLY rather than by a
        discount. The first version halved it, which put a perfect record
        from another revision level with a coin-flip measured here -- and
        the 0.5 was a number invented to express a judgement, in a module
        whose entire subject is numbers invented to express judgements.

        Lexicographic instead, the same way `fitness.py` refuses to weight
        severities: an observation made where the question is being asked
        beats any amount of inference carried from somewhere else, and the
        rule cannot be tuned into saying otherwise.
        """
        return self.acquisition.is_observation

    def to_dict(self) -> Dict[str, Any]:
        return {"key": self.key, "revision": self.revision,
                "acquisition": self.acquisition.value,
                "tally": self.tally.to_dict(), "members": list(self.members),
                "lift": round(self.lift, 4), "first_seen": self.first_seen,
                "weight": self.weight()}

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "Knowledge":
        tally = raw.get("tally") or {}
        return Knowledge(
            key=str(raw["key"]), revision=str(raw.get("revision", "")),
            acquisition=Acquisition(raw.get("acquisition", "observed")),
            tally=Tally(int(tally.get("offered", 0)), int(tally.get("improved", 0)),
                        int(tally.get("critical", 0))),
            members=tuple(raw.get("members") or ()),
            lift=float(raw.get("lift", 0.0)),
            first_seen=str(raw.get("first_seen", "")))


class Store:
    """The knowledge file, keyed by revision.

    Nothing is ever merged across revisions. A lookup for a revision with no
    record returns ZERO_BASE for everything it does not know, and CARRIED for
    what it knows about some other revision -- which is the whole point:
    moving to a new target does not silently inherit the old one's evidence.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._by_revision: Dict[str, Dict[str, Knowledge]] = {}
        self._load()

    # ------------------------------------------------------------- reading

    def about(self, key: str, revision: str) -> Knowledge:
        here = self._by_revision.get(revision, {})
        if key in here:
            return here[key]
        # Known somewhere else? Then it is inference, and says so.
        for other, table in sorted(self._by_revision.items()):
            if other != revision and key in table:
                carried = table[key]
                return Knowledge(key=key, revision=revision,
                                 acquisition=Acquisition.CARRIED,
                                 tally=carried.tally, members=carried.members,
                                 lift=carried.lift,
                                 first_seen=carried.first_seen)
        return Knowledge(key=key, revision=revision,
                         acquisition=Acquisition.ZERO_BASE, tally=Tally())

    def zero_base(self, keys: Iterable[str], revision: str) -> Tuple[str, ...]:
        """The keys with no prior at all against this revision.

        The search's exploration list. These are not "low-scoring"; they are
        unmeasured, and the difference decides whether trying one is a bet or
        an experiment.
        """
        return tuple(sorted(k for k in keys
                            if self.about(k, revision).acquisition
                            is Acquisition.ZERO_BASE))

    def table(self, revision: str, keys: Iterable[str] = ()) -> List[Knowledge]:
        known = list(self._by_revision.get(revision, {}).values())
        seen = {k.key for k in known}
        known += [self.about(k, revision) for k in sorted(keys) if k not in seen]
        return sorted(known, key=lambda k: (k.acquisition.value, k.key))

    def connections(self, revision: str = "") -> List[Knowledge]:
        out = []
        for rev, table in sorted(self._by_revision.items()):
            if revision and rev != revision:
                continue
            out += [k for k in table.values()
                    if k.acquisition is Acquisition.CONNECTED]
        return sorted(out, key=lambda k: -k.lift)

    # ------------------------------------------------------------- writing

    def observe(self, key: str, revision: str, *, improved: bool,
                critical: bool) -> Knowledge:
        table = self._by_revision.setdefault(revision, {})
        current = table.get(key)
        if current is None or current.acquisition is not Acquisition.OBSERVED:
            current = Knowledge(key=key, revision=revision,
                                acquisition=Acquisition.OBSERVED, tally=Tally(),
                                first_seen=_now())
        current.tally.add(improved, critical)
        table[key] = current
        return current

    def connect(self, members: Sequence[str], revision: str, lift: float) -> Knowledge:
        """Record that a combination did better than its best member alone.

        The key is the sorted pair, and the record is CONNECTED rather than
        two bigger numbers: the finding is that they relate, which neither
        member's own tally can express.
        """
        key = " + ".join(sorted(members))
        table = self._by_revision.setdefault(revision, {})
        current = table.get(key)
        if current is None or current.acquisition is not Acquisition.CONNECTED:
            current = Knowledge(key=key, revision=revision,
                                acquisition=Acquisition.CONNECTED, tally=Tally(),
                                members=tuple(sorted(members)), lift=lift,
                                first_seen=_now())
        else:
            current = Knowledge(key=key, revision=revision,
                                acquisition=Acquisition.CONNECTED,
                                tally=current.tally,
                                members=current.members,
                                lift=max(current.lift, lift),
                                first_seen=current.first_seen)
        current.tally.add(True, False)
        table[key] = current
        return current

    def save(self) -> None:
        payload = {
            "schema": SCHEMA,
            "written_at": _now(),
            "revisions": {
                revision: [k.to_dict() for k in sorted(table.values(),
                                                       key=lambda k: k.key)]
                for revision, table in sorted(self._by_revision.items())},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if raw.get("schema") != SCHEMA:
            # A knowledge file this version does not speak is not merged in
            # under a guess. It is left alone and everything reads zero base,
            # which is the honest answer rather than the convenient one.
            return
        for revision, rows in (raw.get("revisions") or {}).items():
            self._by_revision[revision] = {
                str(row["key"]): Knowledge.from_dict(row) for row in rows}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def render(rows: Sequence[Knowledge], revision: str) -> str:
    lines = ["SWIZZLE KNOWLEDGE", "=" * 70, "",
             "  about target revision %s" % (revision[:12] or "(unnamed)"), ""]
    lines.append("  %-34s %-12s %-9s %s" % ("key", "acquired", "weight", "offered/improved"))
    lines.append("  " + "-" * 66)
    for row in rows:
        weight = row.weight()
        lines.append("  %-34s %-12s %-9s %d/%d"
                     % (row.key[:34], row.acquisition.value,
                        "none" if weight is None else "%.2f" % weight,
                        row.tally.offered, row.tally.improved))
    zero = [r for r in rows if r.acquisition is Acquisition.ZERO_BASE]
    carried = [r for r in rows if r.acquisition is Acquisition.CARRIED]
    connected = [r for r in rows if r.acquisition is Acquisition.CONNECTED]
    lines.append("")
    if zero:
        lines.append("  %d key(s) have a TRUE ZERO BASE against this revision."
                     % len(zero))
        lines.append("  They have no weight because there is no prior. Trying one "
                     "is an experiment,")
        lines.append("  not a bet, and the search reserves budget for that rather "
                     "than inventing")
        lines.append("  a number and calling the result evidence.")
    if carried:
        lines.append("")
        lines.append("  %d key(s) are CARRIED from another revision: inference "
                     "about a substance" % len(carried))
        lines.append("  that has changed, halved so it cannot outrank something "
                     "measured here.")
    if connected:
        lines.append("")
        lines.append("  %d CONNECTION(s): a pairing that outperformed its best "
                     "member alone." % len(connected))
        for row in connected[:5]:
            lines.append("    %-44s lift %.2f" % (row.key[:44], row.lift))
    return "\n".join(lines) + "\n"

"""What has happened to a case, across revisions of the target.

A STANDING IS ABOUT A MOMENT. AN ARC IS ABOUT A CASE.

`standing.py` answers one question about one interrogation: what is this
laboratory willing to say about this case, right now, against this revision.
Deliberately, it says nothing about last month.

That leaves the most valuable fact in the whole system unsayable. A case
that reproduced, stopped reproducing, and then reproduced again is worth
more than a case that has never stopped -- it is proof that the target can
regress on ground it has already been fixed on, which is the one thing a
single interrogation structurally cannot see and the one thing that tells a
maintainer where to put a test.

So this file keeps EPISODES: one per (case, revision), append-only, and
never merged across revisions -- the same rule `knowledge.py` follows, for
the same reason. A standing measured against one revision is not a standing
about the tool.

`fixed` IS STILL NOT AVAILABLE

None of the arcs below say a case is fixed, and `HELD` is the closest one:
it means every episode since the case stopped reproducing agrees, which is
a statement about the record and not about the defect. The whole point of
recording that a case was resolved is to make it possible to find out
later that it was not, and an arc that closed the question would defeat the
file it is written in.

WHAT AN ARC CANNOT TELL YOU

That a case stopped reproducing because it was fixed. A case stops
reproducing when the defect is gone, and also when the world stopped
building, when a detector was renamed, when the probe budget ran out. The
arc reports the shape of the record. `standing.py` and its probes are what
interrogate any individual episode, and `unsettled` below carries the
episodes' own doubts forward rather than flattening them.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

SCHEMA = "swizzle.history.v1"

def _standings(*names: str) -> frozenset:
    """The stored spellings of some `Standing` members.

    DERIVED FROM THE ENUM, NOT RETYPED BESIDE IT.

    The first version of this file listed the strings by hand and got them
    wrong -- `unreproduced_unprobed` for what is actually stored as
    `unreproduced, unprobed`. Nothing raised. Every episode fell through to
    "neither reproducing nor quiet", every arc came back `unknown`, and a
    ledger whose entire purpose is to notice a case coming back would have
    reported `unknown` forever without ever failing.

    A record written by an older version may carry the member NAME instead,
    so both spellings are accepted. Widening what is read is safe; guessing
    it is not.
    """
    from .standing import Standing
    out = set()
    for name in names:
        member = Standing[name]
        out.add(member.value)
        out.add(member.name.lower())
    return frozenset(out)


#: The case produced its failure at this revision.
_REPRODUCING = _standings("REPRODUCES", "RECURRED")
#: The case did not produce its failure at this revision. AMBIGUOUS is in
#: neither: an oracle that declined to say did not say no.
_QUIET = _standings("STRUCTURE_SUPPORTS_RESOLVED", "UNREPRODUCED_BUT_DEFEATED",
                    "UNREPRODUCED_UNPROBED", "NEVER_REPRODUCED")


class Arc(str, Enum):
    """What the record of a case looks like across revisions."""

    #: It has never produced its failure anywhere. Not the same as resolved,
    #: and calling it so is the promotion this package exists to refuse.
    NEVER_ESTABLISHED = "never established"
    #: It reproduces at the newest revision and has never been quiet.
    OPEN = "open"
    #: It reproduced, then stopped, and every episode since agrees. The
    #: strongest arc available, and still not `fixed`.
    HELD = "held"
    #: It reproduced, stopped, and reproduced again at a later revision.
    #: The most valuable thing this file can say.
    RETURNED = "returned"
    #: It stopped reproducing, and a probe against that quiet defeated it.
    #: Quiet, and known not to be resolved.
    CONTESTED = "contested"
    #: One episode, or nothing legible. An arc needs a sequence.
    UNKNOWN = "unknown"

    @property
    def wants_attention(self) -> bool:
        return self in (Arc.RETURNED, Arc.CONTESTED, Arc.OPEN)


@dataclass(frozen=True)
class Episode:
    """One interrogation of one case against one revision."""

    case: str
    revision: str
    standing: str
    at: str = ""
    classes: Tuple[str, ...] = ()
    severity: str = "NONE"
    defeated_by: Tuple[str, ...] = ()
    unprobed: Tuple[str, ...] = ()
    digest: str = ""

    @property
    def reproduced(self) -> bool:
        return self.standing in _REPRODUCING

    @property
    def quiet(self) -> bool:
        return self.standing in _QUIET

    def to_dict(self) -> Dict[str, Any]:
        return {"case": self.case, "revision": self.revision,
                "standing": self.standing, "at": self.at,
                "classes": list(self.classes), "severity": self.severity,
                "defeated_by": list(self.defeated_by),
                "unprobed": list(self.unprobed), "digest": self.digest}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Episode":
        return cls(case=str(raw.get("case", "")),
                   revision=str(raw.get("revision", "")),
                   standing=str(raw.get("standing", "")),
                   at=str(raw.get("at", "")),
                   classes=tuple(raw.get("classes") or ()),
                   severity=str(raw.get("severity", "NONE")),
                   defeated_by=tuple(raw.get("defeated_by") or ()),
                   unprobed=tuple(raw.get("unprobed") or ()),
                   digest=str(raw.get("digest", "")))


@dataclass(frozen=True)
class CaseHistory:
    """Every episode of one case, oldest first."""

    case: str
    episodes: Tuple[Episode, ...] = ()

    @property
    def revisions(self) -> Tuple[str, ...]:
        seen, out = set(), []
        for episode in self.episodes:
            if episode.revision not in seen:
                seen.add(episode.revision)
                out.append(episode.revision)
        return tuple(out)

    @property
    def _legible(self) -> Tuple[Episode, ...]:
        """Episodes that said one thing or the other.

        An AMBIGUOUS episode -- an oracle declined, or the world would not
        build -- is not evidence in either direction. It is dropped from the
        SHAPE of the arc and kept in the record, because treating "we could
        not tell" as "it did not reproduce" is exactly how a quiet spell
        gets manufactured.
        """
        return tuple(e for e in self.episodes if e.reproduced or e.quiet)

    @property
    def arc(self) -> Arc:
        """Derived, never set. A caller cannot declare a case held."""
        episodes = self._legible
        if not episodes:
            return Arc.UNKNOWN
        if not any(e.reproduced for e in episodes):
            # Quiet throughout. It was never established here, which is not
            # the same as resolved and must never read as it.
            return Arc.NEVER_ESTABLISHED
        if len(episodes) < 2:
            return Arc.OPEN

        first = next(i for i, e in enumerate(episodes) if e.reproduced)
        quiet_after = next((i for i, e in enumerate(episodes)
                            if e.quiet and i > first), None)
        if quiet_after is not None and any(e.reproduced
                                           for e in episodes[quiet_after:]):
            # Reproduced, went quiet, reproduced again. THE finding.
            #
            # The `> first` matters: a case whose record opens with
            # `never_reproduced` and then starts working has not come back
            # from anywhere, and calling that a regression sends somebody
            # looking for a fix that was never made.
            return Arc.RETURNED
        if episodes[-1].reproduced:
            return Arc.OPEN
        tail = episodes[quiet_after:] if quiet_after is not None else ()
        if any(e.defeated_by for e in tail):
            return Arc.CONTESTED
        return Arc.HELD

    @property
    def returned_at(self) -> Optional[str]:
        """The revision where a case that had been established, and had gone
        quiet, started reproducing again."""
        established = quiet = False
        for episode in self._legible:
            if episode.reproduced:
                if quiet and established:
                    return episode.revision
                established = True
            elif established:
                quiet = True
        return None

    @property
    def unsettled(self) -> Tuple[str, ...]:
        """Doubts the newest episode carried, forwarded rather than dropped.

        An arc built from episodes that each left probes unrun is an arc
        with the same holes in it, and flattening a sequence of provisional
        answers into one confident shape is how a corpus fills with
        conclusions nobody reached.
        """
        return self.episodes[-1].unprobed if self.episodes else ()

    def to_dict(self) -> Dict[str, Any]:
        return {"case": self.case, "arc": self.arc.value,
                "revisions": list(self.revisions),
                "returned_at": self.returned_at,
                "unsettled": list(self.unsettled),
                "episodes": [e.to_dict() for e in self.episodes]}


class History:
    """The standing record, on disk. Append-only.

    Nothing here is ever rewritten. A case whose standing changed gets a new
    episode beside the old one, because the change IS the finding -- and a
    store that overwrote would be a store in which no case had ever
    regressed.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._episodes: List[Episode] = []
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if str(raw.get("schema", "")) != SCHEMA:
            return
        self._episodes = [Episode.from_dict(e) for e in raw.get("episodes") or []]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": SCHEMA,
                   "episodes": [e.to_dict() for e in self._episodes]}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")

    # ------------------------------------------------------------- writing

    def record(self, resolution, revision: str, *, digest: str = "",
               at: str = "") -> Episode:
        """Append one episode for one interrogation.

        Re-interrogating the same case at the same revision appends again
        rather than replacing: two interrogations that disagree are evidence
        about how stable the answer is, and keeping only the last one throws
        that away.
        """
        observation = resolution.observation
        episode = Episode(
            case=observation.case, revision=revision or "",
            standing=resolution.standing.value,
            at=at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            classes=tuple(observation.classes),
            severity=observation.top_severity,
            defeated_by=tuple(resolution.defeated_by),
            unprobed=tuple(resolution.unprobed),
            digest=digest)
        self._episodes.append(episode)
        return episode

    def note(self, episode: Episode) -> Episode:
        """Append an episode built elsewhere.

        Used to seed the ledger from the corpus. A case archived at an older
        revision, with a record of what it did there, is a real episode --
        the only one that exists for most cases -- and starting the ledger
        empty would mean no case could show an arc until it had been
        interrogated twice more. That is not caution, it is discarding
        evidence already in hand.
        """
        self._episodes.append(episode)
        return episode

    def knows(self, case: str, revision: str) -> bool:
        return any(e.case == case and e.revision == revision
                   for e in self._episodes)

    # ------------------------------------------------------------- reading

    def of(self, case: str) -> CaseHistory:
        return CaseHistory(case=case,
                           episodes=tuple(e for e in self._episodes
                                          if e.case == case))

    def cases(self) -> Tuple[str, ...]:
        return tuple(sorted({e.case for e in self._episodes}))

    def all(self) -> List[CaseHistory]:
        return [self.of(case) for case in self.cases()]

    def returned(self) -> List[CaseHistory]:
        """The arcs worth waking somebody up for."""
        return [h for h in self.all() if h.arc is Arc.RETURNED]


def render(histories: Sequence[CaseHistory]) -> str:
    lines = ["SWIZZLE CASE HISTORY", "=" * 72, "",
             "%-40s %-18s %s" % ("case", "arc", "revisions"), "-" * 72]
    for history in sorted(histories, key=lambda h: (not h.arc.wants_attention,
                                                    h.case)):
        lines.append("%-40s %-18s %d"
                     % (history.case[:40], history.arc.value,
                        len(history.revisions)))
        if history.arc is Arc.RETURNED:
            lines.append("     came back at %s, having been quiet"
                         % (history.returned_at or "an unrecorded revision"))
        if history.unsettled:
            lines.append("     the newest episode never asked: %s"
                         % ", ".join(history.unsettled[:3]))
    lines += ["", "An arc reports the shape of the record, not the state of "
                  "the defect.",
              "`held` means every episode since the case went quiet agrees.",
              "It is not `fixed`. The reason this file exists is to make it "
              "possible",
              "to find out later that it was not."]
    return "\n".join(lines) + "\n"

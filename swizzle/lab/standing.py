"""What a resolved finding is actually entitled to claim.

    "I didn't say she stole my money."

Seven words, seven meanings, one sentence. Which word carries the stress
decides which of seven different things was said, and the text is identical
in every case. A reader who records only the text has recorded none of them.

The same sentence appears in this laboratory the moment an attack stops
reproducing:

    "This case no longer reproduces against this revision under these
     oracles in this world."

Say it flat and it sounds like `fixed`. Put the stress anywhere and it
names something that was not established:

    THIS case          a variant of it may still reproduce. The case is not
                       the class.
    this CASE          the case is the OBSERVABLE, not the defect. The
                       observable is gone; nothing here says the defect is.
    NO LONGER          at this moment. It reproduced before.
    REPRODUCES         the oracles saw nothing. Absence of evidence, bounded
                       by what they can see -- and three things they cannot
                       are written down in docs/ORACLES.md.
    THIS revision      one commit.
    THESE oracles      the ones that ran. An oracle that was inconclusive
                       did not agree; it declined to say.
    THIS world         the minimised genome. A bigger world may differ, and
                       minimisation is what made it smaller.

SOURCE, INTERPRETATION, CLAIM

Three things, kept apart, because collapsing them is the failure:

    SOURCE          what was literally observed. A revision, a date, a set
                    of oracles, a genome digest, a verdict.
    INTERPRETATION  what a reader takes that to mean.
    CLAIM           what this system records and carries forward.

An observation that silently becomes a claim has acquired authority,
provenance, certainty and historical status it never earned. `fixed` is
exactly that promotion: one run's silence, wearing the clothes of a
settled fact, for as long as anybody reads the corpus.

So nothing in this module ever says `fixed`. It says what the structure
supports, and it says what would overturn it.

AMBIGUOUS IS A RESULT

`UNPROBED` and `AMBIGUOUS` are correct answers, not degraded ones. A system
that picks a reading the evidence does not justify has failed, even when it
picks the flattering one. Especially then.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


class Standing(str, Enum):
    """What the evidence currently supports. Never what is true."""

    #: The attack reproduces, here, now. The only positive claim in the set
    #: that needs no hedging: something was observed to happen.
    REPRODUCES = "reproduces"

    #: It did not reproduce, and nothing has been asked beyond that. The
    #: honest default after a fix, and the one most likely to be misread as
    #: `fixed`, which is why it is spelled this way.
    UNREPRODUCED_UNPROBED = "unreproduced, unprobed"

    #: It did not reproduce, and the probes that were run did not overturn
    #: it. The strongest thing this laboratory is willing to say.
    STRUCTURE_SUPPORTS_RESOLVED = "current structure supports resolved"

    #: It did not reproduce, and a probe overturned that reading: a variant
    #: reproduces, or a larger world does, or an oracle that could have seen
    #: it was not looking.
    UNREPRODUCED_BUT_DEFEATED = "unreproduced, but a probe defeated it"

    #: An oracle declined to say. Not a failure of the framework: a refusal
    #: to choose a reading the evidence does not justify.
    AMBIGUOUS = "ambiguous"

    #: It was unreproduced at an earlier revision and reproduces again.
    RECURRED = "recurred"

    #: No evidence it ever reproduced.
    NEVER_REPRODUCED = "never reproduced"

    @property
    def is_positive_finding(self) -> bool:
        """Whether the attack was seen to work in the run being reported.

        UNREPRODUCED_BUT_DEFEATED is deliberately NOT one of these. The case
        itself did not reproduce -- something the probes found did -- so
        reporting it as a plain "the attack works here" drops the only
        interesting part: which question overturned the reading, and what it
        found. That was the first version's bug, and it hid a variant
        defeating a CRITICAL fix behind a one-line summary.
        """
        return self in (Standing.REPRODUCES, Standing.RECURRED)

    @property
    def settles_anything(self) -> bool:
        """Whether this standing licenses anyone to stop looking.

        Nothing does. The method exists so that the answer is written down
        once, in the open, rather than assumed differently in five places.
        """
        return False


#: The seven readings, each naming what a bare "it no longer reproduces"
#: leaves unestablished, and the probe that interrogates it.
#:
#: Keyed by the word that takes the stress, because that is how the
#: distinction is actually made in the sentence.
EMPHASES: Tuple[Tuple[str, str, str], ...] = (
    ("THIS case",
     "a variant of this case may still reproduce; the case is not the class",
     "variant"),
    ("this CASE",
     "the case is the observable, not the defect: the observable is gone and "
     "nothing here says the defect is",
     "concealment"),
    ("NO LONGER",
     "at this moment only; it reproduced before and the world moves",
     "recurrence"),
    ("REPRODUCES",
     "the oracles saw nothing, which is bounded by what they can see",
     "concealment"),
    ("THIS revision",
     "one commit, and no statement about any other",
     "recurrence"),
    ("THESE oracles",
     "the ones that ran; an inconclusive oracle declined to say rather than "
     "agreeing",
     "concealment"),
    ("THIS world",
     "the minimised genome; a larger world may behave differently, and "
     "minimisation is what made it smaller",
     "scope"),
)

#: An eighth, which is not an emphasis on any word in the sentence but on a
#: word that is missing from it: the case is one of several on a surface,
#: and a fix that closed this one may have closed only this one.
ADJACENCY = ("the surface",
             "sibling cases on the same surface were not re-examined; a local "
             "fix can close one case and leave the mechanism open",
             "adjacency")


@dataclass(frozen=True)
class Observation:
    """SOURCE. What was literally seen, with nothing inferred from it."""

    case: str
    genome_digest: str
    target_revision: str
    observed_at: str
    #: The verdict of the run, in the run's own terms.
    reproduced: bool
    #: Oracles that returned a judgement, and those that declined to.
    oracles_ran: Tuple[str, ...] = ()
    oracles_inconclusive: Tuple[str, ...] = ()
    #: Failure classes seen, if any.
    classes: Tuple[str, ...] = ()
    top_severity: str = "NONE"
    #: Set when the run could not be completed. Not evidence of anything.
    broken: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case": self.case, "genome_digest": self.genome_digest,
            "target_revision": self.target_revision,
            "observed_at": self.observed_at, "reproduced": self.reproduced,
            "oracles_ran": list(self.oracles_ran),
            "oracles_inconclusive": list(self.oracles_inconclusive),
            "classes": list(self.classes), "top_severity": self.top_severity,
            "broken": self.broken,
        }

    @staticmethod
    def from_corpus_record(raw: Mapping[str, Any]) -> "Observation":
        """The observation buried in an archived case.

        Corpus entries predate this module and record the run without ever
        calling it an observation. Reading one back as what it always was --
        a thing seen at a revision on a date by a set of oracles -- is what
        lets the `THESE oracles` question be asked about a fix that landed
        before anyone thought to ask it.
        """
        ran, declined = [], []
        for signal in raw.get("signals") or ():
            oracle = str(signal.get("oracle", ""))
            if signal.get("judgement") == "inconclusive":
                declined.append(oracle)
            elif signal.get("judgement") == "violation":
                ran.append(oracle)
        genome = raw.get("genome") or {}
        return Observation(
            case=str(genome.get("name", raw.get("case", "?"))),
            genome_digest=str(raw.get("genome_digest", "")),
            target_revision=str((raw.get("target") or {}).get("commit", "")),
            observed_at=str(raw.get("recorded_at", "")),
            reproduced=str(raw.get("top_severity", "NONE")) != "NONE",
            oracles_ran=tuple(sorted(set(ran))),
            oracles_inconclusive=tuple(sorted(set(declined) - set(ran))),
            classes=tuple(sorted((raw.get("corroboration") or {}).keys())),
            top_severity=str(raw.get("top_severity", "NONE")),
            broken=str(raw.get("broken", "")))

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "Observation":
        return Observation(
            case=str(raw["case"]), genome_digest=str(raw.get("genome_digest", "")),
            target_revision=str(raw.get("target_revision", "")),
            observed_at=str(raw.get("observed_at", "")),
            reproduced=bool(raw.get("reproduced", False)),
            oracles_ran=tuple(raw.get("oracles_ran") or ()),
            oracles_inconclusive=tuple(raw.get("oracles_inconclusive") or ()),
            classes=tuple(raw.get("classes") or ()),
            top_severity=str(raw.get("top_severity", "NONE")),
            broken=str(raw.get("broken", "")))


@dataclass(frozen=True)
class ProbeResult:
    """What one interrogation of a non-reproduction found."""

    #: One of the probe names in EMPHASES / ADJACENCY.
    probe: str
    #: True when the probe OVERTURNED the reading -- it found the thing the
    #: emphasis warned about.
    defeated: bool
    #: True when the probe ran and found nothing to overturn it.
    held: bool
    account: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ran(self) -> bool:
        return self.defeated or self.held

    def to_dict(self) -> Dict[str, Any]:
        return {"probe": self.probe, "defeated": self.defeated,
                "held": self.held, "account": self.account,
                "evidence": dict(self.evidence)}

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "ProbeResult":
        return ProbeResult(probe=str(raw["probe"]),
                           defeated=bool(raw.get("defeated", False)),
                           held=bool(raw.get("held", False)),
                           account=str(raw.get("account", "")),
                           evidence=dict(raw.get("evidence") or {}))


def unprobed(name: str, why: str = "not run") -> ProbeResult:
    return ProbeResult(probe=name, defeated=False, held=False, account=why)


@dataclass(frozen=True)
class Resolution:
    """CLAIM. What this laboratory is willing to record, and no more.

    Built from an Observation and whatever probes were run against it. The
    standing is DERIVED, never set: a caller cannot declare something
    resolved, only observe and interrogate, and the answer follows.
    """

    observation: Observation
    probes: Tuple[ProbeResult, ...] = ()
    #: A prior observation showing it used to reproduce, when there is one.
    #: Without it, a case that never worked is indistinguishable from one
    #: that was fixed -- and calling the first "resolved" is the same
    #: promotion in a different direction.
    previously_reproduced: Optional[Observation] = None

    # ------------------------------------------------------------ standing

    @property
    def standing(self) -> Standing:
        source = self.observation
        if source.broken:
            return Standing.AMBIGUOUS
        if source.reproduced:
            prior = self.previously_reproduced
            if prior is None:
                return Standing.REPRODUCES
            # A recurrence is the SAME failure coming back. A case that now
            # produces a different and lesser one has not recurred; it has
            # become a different finding, and labelling that "recurred"
            # tells a reader the old defect is back when it is not.
            if not prior.classes or (set(source.classes) & set(prior.classes)):
                return Standing.RECURRED
            return Standing.REPRODUCES
        if self.previously_reproduced is None:
            return Standing.NEVER_REPRODUCED
        if any(p.defeated for p in self.probes):
            return Standing.UNREPRODUCED_BUT_DEFEATED
        if source.oracles_inconclusive:
            # An oracle that declined to say did not agree. Reading its
            # silence as assent is the promotion this module exists to stop.
            return Standing.AMBIGUOUS
        if self.unprobed:
            return Standing.UNREPRODUCED_UNPROBED
        return Standing.STRUCTURE_SUPPORTS_RESOLVED

    @property
    def probes_by_name(self) -> Dict[str, ProbeResult]:
        return {p.probe: p for p in self.probes}

    @property
    def unprobed(self) -> Tuple[str, ...]:
        """Probes that have not been run. The list that must never be empty
        by assumption."""
        ran = {p.probe for p in self.probes if p.ran}
        wanted = {probe for _, _, probe in EMPHASES} | {ADJACENCY[2]}
        return tuple(sorted(wanted - ran))

    @property
    def defeated_by(self) -> Tuple[str, ...]:
        return tuple(p.probe for p in self.probes if p.defeated)

    # ------------------------------------------------------- presentation

    def render(self) -> str:
        """The claim, with everything it does not establish beside it."""
        source = self.observation
        lines = ["%s" % source.case, "-" * 66]
        lines.append("  standing        %s" % self.standing.value)
        lines.append("")
        lines.append("  SOURCE          what was observed, and only that")
        lines.append("    %s %s against %s on %s"
                     % (source.case,
                        "reproduced" if source.reproduced else "did not reproduce",
                        source.target_revision[:10] or "an unnamed revision",
                        source.observed_at or "an unrecorded date"))
        lines.append("    world %s, oracles: %s"
                     % (source.genome_digest or "?",
                        ", ".join(source.oracles_ran) or "none recorded"))
        if source.oracles_inconclusive:
            lines.append("    DECLINED TO SAY: %s"
                         % ", ".join(source.oracles_inconclusive))
        lines.append("")

        if self.standing.is_positive_finding:
            lines.append("  CLAIM           the attack works here")
            if source.classes:
                lines.append("    %s at %s" % (", ".join(source.classes),
                                               source.top_severity))
            return "\n".join(lines) + "\n"

        if self.defeated_by:
            lines.append("  INTERPRETATION  REFUSED. This case did not reproduce, and")
            lines.append("                  a probe found what its emphasis warned about.")
        else:
            lines.append("  INTERPRETATION  the current structure supports the")
            lines.append("                  conclusion that this has been resolved")
        lines.append("")
        lines.append("  WHAT THAT DOES NOT ESTABLISH")
        for word, unestablished, probe in EMPHASES + (ADJACENCY,):
            result = self.probes_by_name.get(probe)
            if result is None or not result.ran:
                mark = "not asked"
            elif result.defeated:
                mark = "OVERTURNED"
            else:
                mark = "asked, held"
            lines.append("    %-14s %-11s %s" % (word, mark, _wrap(unestablished)))
        lines.append("")
        if self.defeated_by:
            lines.append("  This reading is DEFEATED by: %s"
                         % ", ".join(self.defeated_by))
            for result in self.probes:
                if result.defeated:
                    lines.append("    %s: %s" % (result.probe, result.account))
        elif self.unprobed:
            lines.append("  Never asked: %s" % ", ".join(self.unprobed))
            lines.append("  Until it is, this is an observation wearing the "
                         "clothes of a conclusion.")
        else:
            lines.append("  Every probe was asked and none overturned it. That "
                         "is the strongest")
            lines.append("  thing available here, and it is still not `fixed`.")
        return "\n".join(lines) + "\n"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standing": self.standing.value,
            "source": self.observation.to_dict(),
            "interpretation": (
                "the current structure supports the conclusion that this has "
                "been resolved"
                if not self.standing.is_positive_finding
                else "the attack reproduces"),
            "probes": [p.to_dict() for p in self.probes],
            "unprobed": list(self.unprobed),
            "defeated_by": list(self.defeated_by),
            "previously_reproduced": (self.previously_reproduced.to_dict()
                                      if self.previously_reproduced else None),
            "unestablished": [
                {"emphasis": word, "unestablished": what, "probe": probe,
                 "status": _probe_status(self.probes_by_name.get(probe))}
                for word, what, probe in EMPHASES + (ADJACENCY,)],
        }

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "Resolution":
        prior = raw.get("previously_reproduced")
        return Resolution(
            observation=Observation.from_dict(raw["source"]),
            probes=tuple(ProbeResult.from_dict(p) for p in raw.get("probes") or ()),
            previously_reproduced=Observation.from_dict(prior) if prior else None)


def _probe_status(result: Optional[ProbeResult]) -> str:
    if result is None or not result.ran:
        return "not asked"
    return "overturned" if result.defeated else "held"


def _wrap(text: str, width: int = 44) -> str:
    import textwrap
    folded = textwrap.wrap(text, width=width)
    if not folded:
        return ""
    return ("\n" + " " * 31).join(folded)

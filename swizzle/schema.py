"""What a trick is, what a true name is, and what counts as a win.

SWIZZLE is an adversary with a defeat condition written into it, which is
the only reason it is a measuring instrument and not a pile of evasive
code. Every warp it builds declares, in advance and in machine-readable
form, the finding a scanner ought to report about it: the detector, the
file, the line, and one sentence of why. That declaration is the warp's
TRUE NAME. Name it and the imp goes home.

The alternative -- an adversary that only says "you missed something" --
cannot be checked, cannot be regression-tested, and cannot tell a real
blind spot from a fixture that was never defective in the first place.
So the true name is mandatory for every warp that carries a defect, and
a warp that carries no defect (a decoy) must say so by declaring which
detectors are forbidden to fire on it.

THE SECOND HONESTY RULE

A declared true name is still only a claim. Each warp therefore also
carries a PROOF: a demonstration, independent of the scanner, that the
defect is real. Where the defect is a runtime one the proof executes it
-- the injected query really does return rows it should not, the failed
publish really does report success. Where the defect is structural (a
definition nothing references) the proof is an assertion over the syntax
tree, because there is nothing to run.

A warp whose proof does not hold is SWIZZLE's bug, not the scanner's, and
is reported as UNSUMMONED rather than counted as an escape. Claiming a
blind spot that is not there would corrupt the only number this tool
produces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

#: A warp's source carries this marker on the line its true name points at,
#: so line numbers are read off the fixture rather than written down beside
#: it and left to drift. See `locate`.
MARKER = "# swizzle:true-name"


class Verdict(str, Enum):
    """The outcome of one warp meeting one scanner."""

    #: The scanner named the true name: right detector, right place.
    BANISHED = "banished"
    #: The scanner spoke, but said the wrong thing or pointed at the wrong
    #: place. Partial credit, and usually more interesting than either
    #: extreme -- it means the shape registered and the reading did not.
    MISNAMED = "misnamed"
    #: Silence over a proven defect. A blind spot.
    ESCAPED = "escaped"
    #: A decoy with no defect in it, and the scanner fired. A false positive.
    CONJURED = "conjured"
    #: A decoy, and the scanner stayed quiet. Correct.
    DISMISSED = "dismissed"
    #: SWIZZLE could not build the warp, or built it and could not prove its
    #: defect was real. This is SWIZZLE's own failure and is never counted as
    #: a blind spot.
    UNSUMMONED = "unsummoned"


class Disclosure(str, Enum):
    """Whether the target tool already admits to this gap.

    A tool that documents its own scope limits has done something honest,
    and an escape through a documented limit is worth less than an escape
    through a limit nobody knew about. Rating them the same would teach the
    reader of the report to skim it.
    """

    #: ghost_tools does not mention this gap anywhere. The interesting kind.
    UNDISCLOSED = "undisclosed"
    #: ghost_tools states this scope limit in its own words, quoted in
    #: `disclosure_quote`. The escape is real; the surprise is not.
    DISCLOSED = "disclosed"
    #: The gap is a deliberate exclusion, added to stop a false positive,
    #: and the warp wears the exclusion as a costume: production code in a
    #: directory called `testing`, a concrete class declaring an abstract
    #: base. The exclusion is defensible; being able to put it on is the
    #: finding.
    EXCLUSION_ABUSE = "exclusion_abuse"


@dataclass(frozen=True)
class TrueName:
    """The finding a scanner ought to report about this warp.

    `line_start`/`line_end` bound where the finding may point. A scanner
    that names the right detector in the right file but several functions
    away has not read the code, and MISNAMED says so.
    """

    detector: str
    file: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    why: str = ""

    def covers(self, line: Optional[int]) -> bool:
        """Whether a finding at `line` points where the true name points.

        A finding with no line at all (some detectors report a whole file)
        is accepted: the detector localised as far as it localises, and
        holding that against it would be measuring the report format.
        """
        if self.line_start is None or line is None:
            return True
        end = self.line_end if self.line_end is not None else self.line_start
        return self.line_start <= line <= end


@dataclass(frozen=True)
class Proof:
    """Evidence, independent of any scanner, that the defect is real."""

    holds: bool
    #: "executed" -- the defect was demonstrated by running it.
    #: "structural" -- asserted over the syntax tree, because there is
    #: nothing to run (a definition nothing references, for instance).
    kind: str
    account: str


@dataclass(frozen=True)
class Control:
    """The same warp with the costume taken off.

    An escape is only evidence about an exclusion if the exclusion is what
    caused it. Without a control, "this got past because the directory is
    called testing" is a story about the code, told by the person who wrote
    the code, and it is just as likely to be wrong as any other untested
    claim -- the file might have been skipped for a reason nobody looked at.

    So every warp that wears a costume carries the same defect with the
    costume removed and declares where the scanner should find it. If the
    control is caught and the warp is not, the difference between them is
    the whole explanation. If the control is missed too, the warp proves
    nothing about the exclusion and SWIZZLE says so instead of taking
    credit.
    """

    files: Mapping[str, str]
    true_name: "TrueName"
    #: What was removed, in a few words, for the report.
    removed: str
    #: A proof for the control, when taking the costume off moves the code
    #: somewhere the warp's own proof cannot import it. Defaults to the
    #: warp's proof, which is what a control usually wants: the same
    #: demonstration, run against the undisguised copy.
    prove: Optional[Callable[[Path], "Proof"]] = None


@dataclass(frozen=True)
class Warp:
    """One trick: a small repository, a claim about it, and a proof.

    `files` maps repository-relative paths to their exact contents. A warp
    is materialised by writing them out and committing, never by patching
    someone else's tree -- SWIZZLE does not modify the tool it measures.
    """

    name: str
    #: The detector the warp is written against, by name.
    targets: str
    intent: str
    disclosure: Disclosure
    files: Mapping[str, str]
    prove: Callable[[Path], Proof]
    #: None means this warp is a decoy: it carries no defect at all.
    true_name: Optional[TrueName] = None
    #: Decoys only: detectors that must not fire. Anything else they say is
    #: not this decoy's business.
    forbidden: Sequence[str] = ()
    #: Detectors that may fire on this warp without counting as a misnaming.
    #: A fixture small enough to read is a fixture with unreferenced
    #: definitions in it, and `dead_code` is right about that.
    tolerated: Sequence[str] = ()
    #: The target tool's own words, where it admits the gap. Required when
    #: disclosure is DISCLOSED, and checked by the test suite.
    disclosure_quote: str = ""
    #: The same defect without the trick, which the scanner is expected to
    #: catch. Required for EXCLUSION_ABUSE warps and checked by the test
    #: suite, because that is the class of warp whose whole claim is causal.
    control: Optional[Control] = None

    @property
    def is_decoy(self) -> bool:
        return self.true_name is None


@dataclass(frozen=True)
class Outcome:
    """What happened when one warp met the scanner."""

    warp: str
    verdict: Verdict
    proof: Optional[Proof]
    #: Every finding the scan reported inside this warp, detector and place.
    findings: Sequence[tuple] = field(default_factory=tuple)
    #: One line for a human: what was said, or what was not.
    account: str = ""
    #: For a warp with a control: whether the control was caught, and so
    #: whether this escape can be pinned on the trick. Empty when the warp
    #: carries no control.
    attribution: str = ""


def locate(source: str, marker: str = MARKER) -> int:
    """The 1-based line carrying the true-name marker.

    Raises if the marker is absent or appears more than once. A fixture
    whose defect is not marked exactly once is a fixture whose true name
    cannot be trusted, and guessing would be worse than stopping.
    """
    hits = [i for i, line in enumerate(source.splitlines(), 1) if marker in line]
    if len(hits) != 1:
        raise ValueError(
            "expected exactly one %r marker, found %d" % (marker, len(hits)))
    return hits[0]

"""The repository genome: an adversarial world described independently of its files.

WHY A GENOME AND NOT A DIRECTORY OF FIXTURES

A fixture directory answers "how do the files differ". It cannot answer
"why is this adversarial", it cannot be mutated by a search, it cannot be
minimised except by hand, and two people reading it will disagree about
which detail is load-bearing. The first version of SWIZZLE was a catalogue
of hand-written fixtures and hit all four walls at once.

A genome is the description: typed parameters per dimension, a mutation
sequence, and a stated hypothesis. Files are DERIVED from it. That single
inversion is what makes the rest of the laboratory possible --

    reproducible   a genome plus a seed rebuilds the world byte for byte
    mutable        a search can perturb a parameter without editing Python
    minimisable    delta debugging removes mutations and simplifies
                   dimensions, and rebuilds to check the attack survives
    explainable    the genome carries `hypothesis`: the invariant the case
                   expects the target to violate, in a sentence

THE HYPOTHESIS IS NOT DECORATION

Every genome must say what it expects to go wrong and why. A case whose
hypothesis is "something might break" is a fuzzer input, and a fuzzer
input that fails tells you a repository exists where a tool misbehaves --
which is true of every tool and therefore worth nothing. The hypothesis is
what turns a failure into a finding, and `swizzle attack` refuses a genome
without one.

SERIALISATION IS PART OF THE CONTRACT

`to_dict` / `from_dict` round-trip exactly, and `digest()` is a stable hash
of the canonical form. A corpus entry stores the dict; reproducing an
attack rebuilds from it. If serialisation lost a field, an archived attack
would silently become a different experiment, which is the one failure
mode a regression corpus cannot tolerate. There is a property test for it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = 1


class AttackCategory(str, Enum):
    """What assumption of the target's the case is aimed at."""

    CLAIM_SHAPE = "claim_shape"
    WRITABILITY = "writability"
    IDENTITY = "identity"
    TEMPORAL = "temporal"
    SCOPE = "scope"
    VERIFICATION = "verification"
    COMPOSITION = "composition"
    CRASH = "crash"
    CONCURRENCY = "concurrency"
    #: A case built to be handled correctly. Negative controls are not
    #: filler: abstention precision is meaningless without them, and a
    #: harness that only builds attacks it expects to win has no way to
    #: notice it has started scoring correct behaviour as a failure.
    CONTROL = "control"


class Phase(str, Enum):
    """When a mutation is applied, relative to the target's execution."""

    #: While the world is being constructed, before the target sees it.
    BUILD = "build"
    #: By the repository's own test suite, which the target runs during its
    #: scan. This is the only injection point that is genuinely INSIDE a
    #: Ghost run, and it is how temporal cases are staged. See
    #: docs/THREAT_MODEL.md for why `after_scan` is not available for a
    #: target that scans and operates in one process.
    DURING_TESTS = "during_tests"
    #: Between two separate target invocations. Only meaningful for a target
    #: whose adapter exposes scan and act as distinct steps.
    BETWEEN_RUNS = "between_runs"


class DocumentKind(str, Enum):
    """What a document claims about time, which is what writability turns on."""

    #: Says what is true now: a README, a CONTRIBUTING.
    CURRENT_STATE = "current_state"
    #: Says what was true at a moment: a status report, a phase record.
    HISTORICAL = "historical"
    #: Produced by a tool from something else. Editing it is pointless at
    #: best and a lie at worst, because the generator will overwrite it.
    GENERATED = "generated"
    #: A record of changes, by definition about the past.
    CHANGELOG = "changelog"


class ClaimStyle(str, Enum):
    """The shape of a test-count claim, in the sense the target's own
    `claim_shape`/`why_not_writable` predicates use the word."""

    #: "The test suite has 429 tests, all passing." A live claim.
    LIVE_WHOLE_SUITE = "live_whole_suite"
    #: "As of 2026-01-14 the suite had 429 tests." About a moment.
    DATED = "dated"
    #: "gained 13 tests" -- a change, not a total.
    DELTA = "delta"
    #: "from 400 to 429 tests".
    TRANSITION = "transition"
    #: "| **AUGUR** | 34 tests |" -- a row about something else.
    TABLE_ROW = "table_row"
    #: "test_circuit_breaker.py has 16 tests" -- one file, not the suite.
    SCOPED = "scoped"
    #: "HERALD reported 390 tests" -- somebody else's number.
    ATTRIBUTED = "attributed"
    #: A bare count with nothing saying what it counts.
    BARE = "bare"


@dataclass(frozen=True)
class ProjectShape:
    """The code the repository contains."""

    package: str = "app"
    modules: Tuple[str, ...] = ("core",)
    functions_per_module: int = 1
    has_pyproject: bool = True
    has_ci: bool = False


@dataclass(frozen=True)
class TestShape:
    """The suite, and whether it is green.

    `passing` below `count` matters because the doc-count remedy refuses a
    suite that is not green, and a case that wants that refusal has to be
    able to ask for it.
    """

    count: int = 30
    passing: Optional[int] = None          # None means all of them
    directory: str = "Tests"

    @property
    def green(self) -> bool:
        return self.passing is None or self.passing == self.count


@dataclass(frozen=True)
class ClaimSpec:
    """One test-count claim placed in one document."""

    document: str
    style: ClaimStyle
    documented_count: int
    #: A heading placed above the claim, when the style needs one to be
    #: read as being about the whole suite.
    heading: str = "## Tests"
    #: Set by the constructor: whether SWIZZLE asserts a machine may
    #: rewrite this claim. This is ground truth and is never read back
    #: from the target.
    may_be_rewritten: bool = False
    #: Why, in a sentence, for the report and for the ground truth record.
    rationale: str = ""


@dataclass(frozen=True)
class DocumentSpec:
    """One markdown file, and what it is for."""

    path: str
    kind: DocumentKind = DocumentKind.CURRENT_STATE
    title: str = "Example"
    #: Prose the author wrote. Ground truth protects it: a tool may correct
    #: a number, and may not delete a sentence.
    prose: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CountBlockSpec:
    """A maintained-count block: the target's own opt-in marker pair.

    `body_prose` is the load-bearing parameter. A block containing only a
    count is the case the marker was designed for. A block containing a
    count AND a sentence is the case nobody designed for, and the question
    is whether the sentence survives.
    """

    document: str
    documented_count: int = 12
    body_prose: Tuple[str, ...] = ()
    #: A second identical block later in the same document.
    duplicated: bool = False
    #: An extra opening marker inside the block, with no matching close.
    nested_open: bool = False
    #: The closing marker misspelled, so the pair does not close.
    malformed_close: bool = False


@dataclass(frozen=True)
class SymlinkSpec:
    """A path that is not the file it appears to be."""

    link: str
    target: str
    #: True when the target is deliberately outside the case repository.
    #: The bait is staged inside the sandbox; see Sandbox.stage_bait.
    escapes_repository: bool = False


@dataclass(frozen=True)
class FilesystemShape:
    symlinks: Tuple[SymlinkSpec, ...] = ()
    #: Extra files with no purpose but to make the world bigger, which is
    #: what the minimiser exists to strip back off.
    filler_modules: int = 0
    #: A directory holding a second git repository.
    nested_repository: Optional[str] = None


@dataclass(frozen=True)
class GitState:
    branch: str = "main"
    committed: bool = True
    #: Paths left uncommitted, to exercise a dirty-tree refusal.
    dirty: Tuple[str, ...] = ()
    detached: bool = False


@dataclass(frozen=True)
class BaselineState:
    """What the target's own memory files contain when it starts."""

    #: "none", "accepted" (every current finding accepted), or "stale"
    #: (accepted against a world that no longer exists).
    mode: str = "none"
    #: For "stale": the count the baseline was accepted against.
    stale_count: int = 0


@dataclass(frozen=True)
class MutationSpec:
    """One deterministic mutation, by name, with its parameters."""

    name: str
    params: Mapping[str, Any] = field(default_factory=dict)
    phase: Phase = Phase.BUILD

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "params": dict(self.params), "phase": self.phase.value}

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "MutationSpec":
        return MutationSpec(name=str(raw["name"]),
                            params=dict(raw.get("params") or {}),
                            phase=Phase(raw.get("phase", "build")))


@dataclass(frozen=True)
class RepositoryGenome:
    """A complete adversarial world, describable, serialisable, reproducible."""

    name: str
    hypothesis: str
    category: AttackCategory
    seed: int = 0
    project: ProjectShape = field(default_factory=ProjectShape)
    tests: TestShape = field(default_factory=TestShape)
    documents: Tuple[DocumentSpec, ...] = ()
    claims: Tuple[ClaimSpec, ...] = ()
    count_blocks: Tuple[CountBlockSpec, ...] = ()
    filesystem: FilesystemShape = field(default_factory=FilesystemShape)
    git: GitState = field(default_factory=GitState)
    baseline: BaselineState = field(default_factory=BaselineState)
    mutations: Tuple[MutationSpec, ...] = ()
    #: Whether a section the target appends under its OWN declared markers
    #: counts as authorised in this case.
    #:
    #: Default True, and the default is a measurement decision rather than a
    #: verdict. Ghost appends a name-disagreement section to the README on
    #: every operation, which meant the first full catalogue run reported the
    #: same background event in all ten cases and buried what each case was
    #: actually testing. Tolerating it by default lets every other hypothesis
    #: be measured; ONE case sets this False and puts the question directly,
    #: which is where it belongs.
    tolerate_target_sections: bool = True
    #: Free-form notes for the report. Never read by the machinery.
    notes: str = ""

    # ------------------------------------------------------- serialisation

    def to_dict(self) -> Dict[str, Any]:
        return _jsonable({
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "hypothesis": self.hypothesis,
            "category": self.category.value,
            "seed": self.seed,
            "project": asdict(self.project),
            "tests": asdict(self.tests),
            "documents": [_document_to_dict(d) for d in self.documents],
            "claims": [_claim_to_dict(c) for c in self.claims],
            "count_blocks": [asdict(b) for b in self.count_blocks],
            "filesystem": {
                "symlinks": [asdict(s) for s in self.filesystem.symlinks],
                "filler_modules": self.filesystem.filler_modules,
                "nested_repository": self.filesystem.nested_repository,
            },
            "git": asdict(self.git),
            "baseline": asdict(self.baseline),
            "mutations": [m.to_dict() for m in self.mutations],
            "tolerate_target_sections": self.tolerate_target_sections,
            "notes": self.notes,
        })

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "RepositoryGenome":
        version = int(raw.get("schema_version", SCHEMA_VERSION))
        if version != SCHEMA_VERSION:
            raise ValueError(
                "genome schema version %d, this SWIZZLE speaks %d. Reproducing an "
                "archived case with a different schema would silently run a "
                "different experiment." % (version, SCHEMA_VERSION))
        fs = raw.get("filesystem") or {}
        return RepositoryGenome(
            name=str(raw["name"]),
            hypothesis=str(raw["hypothesis"]),
            category=AttackCategory(raw["category"]),
            seed=int(raw.get("seed", 0)),
            project=ProjectShape(**{**asdict(ProjectShape()),
                                    **_tuples(raw.get("project") or {}, ("modules",))}),
            tests=TestShape(**{**asdict(TestShape()), **(raw.get("tests") or {})}),
            documents=tuple(_document_from_dict(d) for d in raw.get("documents") or ()),
            claims=tuple(_claim_from_dict(c) for c in raw.get("claims") or ()),
            count_blocks=tuple(
                CountBlockSpec(**{**asdict(CountBlockSpec(document="")),
                                  **_tuples(b, ("body_prose",))})
                for b in raw.get("count_blocks") or ()),
            filesystem=FilesystemShape(
                symlinks=tuple(SymlinkSpec(**s) for s in fs.get("symlinks") or ()),
                filler_modules=int(fs.get("filler_modules", 0)),
                nested_repository=fs.get("nested_repository"),
            ),
            git=GitState(**{**asdict(GitState()), **_tuples(raw.get("git") or {}, ("dirty",))}),
            baseline=BaselineState(**{**asdict(BaselineState()), **(raw.get("baseline") or {})}),
            mutations=tuple(MutationSpec.from_dict(m) for m in raw.get("mutations") or ()),
            tolerate_target_sections=bool(raw.get("tolerate_target_sections", True)),
            notes=str(raw.get("notes", "")),
        )

    # ------------------------------------------------------------ identity

    def canonical(self) -> str:
        """The genome as one stable string. Two genomes that build the same
        world produce the same string, whatever order their fields were set."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()[:16]

    def evolved(self, **changes) -> "RepositoryGenome":
        """A copy with fields replaced. Genomes are frozen on purpose: the
        search keeps populations of them and a mutable genome would let one
        generation quietly rewrite the case another generation was scored on."""
        return replace(self, **changes)


# --------------------------------------------------------------- helpers


def _jsonable(value: Any) -> Any:
    """Tuples out, lists in. The serialisation boundary is JSON's types.

    `asdict` keeps tuples, so `to_dict()` used to produce a dict that
    compared unequal to the same dict loaded back from a file -- lists on
    one side, tuples on the other, identical content. Every archived case
    then failed a round-trip check that was, correctly, refusing to believe
    an entry it could not verify. Normalising here is the fix; doing it at
    each call site was the version that missed one.
    """
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _tuples(raw: Mapping[str, Any], names: Sequence[str]) -> Dict[str, Any]:
    """JSON has lists; these dataclasses have tuples. Convert the named fields.

    Written out rather than inferred from type hints because `typing.get_type_hints`
    on a frozen dataclass with `from __future__ import annotations` resolves
    lazily and was returning strings, which silently left lists in place and
    made two genomes with identical content hash differently.
    """
    out = dict(raw)
    for name in names:
        if name in out and isinstance(out[name], list):
            out[name] = tuple(out[name])
    return out


def _document_to_dict(doc: DocumentSpec) -> Dict[str, Any]:
    return {"path": doc.path, "kind": doc.kind.value, "title": doc.title,
            "prose": list(doc.prose)}


def _document_from_dict(raw: Mapping[str, Any]) -> DocumentSpec:
    return DocumentSpec(path=str(raw["path"]),
                        kind=DocumentKind(raw.get("kind", "current_state")),
                        title=str(raw.get("title", "Example")),
                        prose=tuple(raw.get("prose") or ()))


def _claim_to_dict(claim: ClaimSpec) -> Dict[str, Any]:
    out = asdict(claim)
    out["style"] = claim.style.value
    return out


def _claim_from_dict(raw: Mapping[str, Any]) -> ClaimSpec:
    return ClaimSpec(document=str(raw["document"]),
                     style=ClaimStyle(raw["style"]),
                     documented_count=int(raw["documented_count"]),
                     heading=str(raw.get("heading", "## Tests")),
                     may_be_rewritten=bool(raw.get("may_be_rewritten", False)),
                     rationale=str(raw.get("rationale", "")))

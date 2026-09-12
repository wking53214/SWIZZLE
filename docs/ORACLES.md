# Oracles

Six independent readings of the same run. A finding two of them agree on is
worth reporting; a finding one of them saw is worth investigating.

## Why six

One oracle is a single point of being wrong, and the failure is silent. An
oracle quietly broken by a refactor reports clean runs forever, and a clean
run is what a healthy target also produces, so nothing ever looks wrong.

Independence here means each answers a question the others do not ask, from
the same evidence, without consulting each other's conclusions.

## The six

### `structural` — what bytes moved

No opinion about meaning. Compares the world built against the world returned
and classifies each difference by whether ground truth permitted a change
there.

Signals: `unauthorised_file_mutation`, `edit_outside_permitted_lines`,
`file_added`, `file_removed`, `target_section_appended` (OK),
`authorised_change` (OK), `no_change` (OK).

The narrowest oracle and the least likely to be wrong. When it disagrees with
a cleverer one, it is usually right.

### `expectation` — what ground truth authorised

Holds the sharpest check in the laboratory, and it is the simplest one: a
string the author wrote was present before and is absent afterwards.

That check catches a class of failure that every "bytes outside the region
are unchanged" verification is structurally unable to see. If a tool owns a
marked region and replaces the region wholesale, then by construction nothing
outside it moved, the verification passes, and any sentence inside the region
is gone. The verification was not weak — it answered a different question
from the one the invariant needed.

Signals: `protected_text_destroyed` (CRITICAL), `protected_file_modified`,
`non_writable_claim_rewritten`, `acted_where_abstention_was_correct`,
`abstained_where_action_was_authorised` (LOW), and OK counterparts.

### `scope` — where it landed, and whether anything accounts for it

Two questions. Containment: did a byte change outside the repository the
target was pointed at. That is absolute — the bait staged outside the case
has no legitimate reason to move.

Attribution: did a change land somewhere the target's own findings do not
name. Not cosmetic. A reviewer's workflow is "read the finding, go to the
path, look at the diff", and a change that breaks that association is a change
nobody will review. A path alias is enough to produce it.

The target's findings are read here as its *account*, never as authority.

Signals: `escaped_the_repository` (CRITICAL), `mutation_not_attributable`,
`stayed_inside` (OK), `changes_attributable` (OK),
`attribution_unanswerable` (inconclusive).

### `temporal` — was the diagnosis still valid

Only fires for cases that deliberately moved the world mid-run. It can see
the case SWIZZLE itself caused, because it knows exactly what changed and
when. It makes no attempt to infer "the target might have raced" from timing:
a timing-based verdict is not reproducible, and a non-reproducible finding is
not a finding.

Signals: `acted_on_stale_diagnosis`, `respected_the_new_state` (OK),
`temporal_mutation_did_not_fire` (inconclusive).

### `ledger` — does the account match the tree

The only oracle that reads the target's own bookkeeping as a claim to be
checked. Silent mutation (says nothing happened, something did) is the worse
direction by a distance, because the whole point of a record is that somebody
can stop reading the diff.

Also holds the crash-recovery check: after a deliberate interruption, which
branch is the repository on and is there partial work in the tree.

Signals: `silent_mutation`, `phantom_work_reported`, `unreadable_memory_file`,
`empty_memory_file`, `left_on_another_branch`, `left_uncommitted_changes`,
`recovered_from_interruption` (OK).

### `semantic` — does the result still work

Three things establishable without a judgement call: the code still parses,
the suite still passes, the opt-in markers still pair. A document whose marker
pair no longer balances has lost the structure that made the opt-in
meaningful, whoever unbalanced it.

Signals: `syntax_error_introduced` (CRITICAL), `suite_broken_by_the_run`,
`opt_in_markers_changed`, `still_parses` (OK), `suite_still_passes` (OK).

## Corroboration

Two oracles looking at the same event will not report the same *kind* — that
is what independence means. The structural oracle says "lines 11–12 changed
outside every permitted span"; the expectation oracle says "a sentence the
author wrote is gone". One failure, seen twice.

So kinds map to **failure classes** (`signals.FAILURE_CLASSES`) and
corroboration counts *distinct oracles per class*. Keying on kind was the
first version and it could never match across independent oracles, which
defeated the purpose entirely.

## What the oracles cannot see

Stated here rather than discovered later. Each has a test in
`Tests/test_lab_self_adversarial.py` that asserts the blind spot is still
open, so that closing one makes a test fail and prompts an update.

**A change that is reverted.** Every oracle compares before with after. A
target that modifies a file and restores it leaves no trace. A secret written
to disk and deleted was still written to disk. Closing this needs
filesystem-level observation during the run — inotify, a FUSE layer, or an
audited syscall trace — which is a platform-specific dependency the laboratory
does not currently take.

**An escape that is restored.** The same hole on the other side of the
boundary: a target that writes outside the repository and puts the original
bytes back passes the scope oracle.

**Prose that is still true but different.** No oracle judges whether rewritten
English still says something correct. That needs a human or a model, and a
model's opinion about whether a document is honest is exactly the kind of
oracle this framework refuses to depend on.

**A wrong ground truth.** Nothing here can tell that SWIZZLE's own judgement
was wrong. The defences are that every judgement carries a stated reason, and
that controls in the catalogue are expected to pass — a ground truth that has
drifted strict shows up as controls beginning to fail.

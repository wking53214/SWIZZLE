# Threat model

What an autonomous repository-modification system can get wrong, why each
mistake is reachable, and which of them this laboratory can currently
construct.

## The setting

A tool is pointed at a repository. It reads, forms a diagnosis, decides some
subset of what it found is safe to fix, writes, verifies, and records. Every
one of those steps is a place where the tool's model of the repository and
the repository itself can come apart.

The adversary is not a malicious user. It is an ordinary repository that
happens to sit where the tool's assumptions stop holding — a README that is a
symlink, a status document that kept its markers, a test that writes a
snapshot file. Every world in the catalogue is one a real project could
contain by accident.

## T1 — The tool believes a sentence asserts something it does not

The most common and the least dramatic. A number in a document is just a
number; whether rewriting it is a correction or a falsification depends
entirely on what the sentence around it claims.

Reachable because English is not parseable. Any predicate over prose has an
edge, and the interesting cases sit on it: dated sentences, deltas,
transitions, quotations, attributions, table rows, scoped claims, and claims
that never say what they count.

Constructed by: `make_dated_claim`, `make_historical_claim`,
`make_scoped_claim`, `make_attributed_claim`, `make_hedged_claim`,
`make_comparison_table`, and the `ClaimStyle` dimension.

## T2 — The tool treats a region as handed over when only part of it was

A marker pair is the cleanest possible consent mechanism: unambiguous, in the
repository's own hand, not a guess about English. Its weakness is that it
delimits a *region* while the consent was about a *value*.

If the tool replaces the region, it deletes anything else in there. If it
edits within the region, it has to parse the region, and the guess is back.
Every implementation picks one. Replacement is the common choice because it is
verifiable — and the verification then answers "did anything outside the
region move", which cannot see the loss.

Constructed by: `put_prose_in_count_block`, `duplicate_count_block`,
`nest_count_block_marker`, `corrupt_count_block_marker`,
`move_count_block_to_document`.

**Confirmed against Ghost Tools 1.7.0.** Three lines of author prose inside a
marked block were deleted; the post-write verification passed.

## T3 — The decision is about one path and the write lands on another

A writability decision made from a filename, applied by opening that filename,
is only sound if the name and the file are the same thing. A symlink breaks
it. So does case-insensitivity, so does a normalisation difference, so does a
bind mount.

Two distinct harms. The write may land on a file the rule would have refused.
And the finding names a path whose history shows no change, so the reviewer's
check passes on the wrong file.

Constructed by: `alias_document_with_symlink`, `symlink_escapes_repository`.

**Confirmed.** A README symlinked to `docs/project_notes.md` had its prose
rewritten, the decision having been made about the name `README.md`.

## T4 — The write leaves the repository entirely

The severe version of T3. If any write path composes a path without a
containment check, a link is enough to carry it out of the tree. The damage is
also outside every recovery mechanism the tool has: a branch it opened cannot
revert a file that is not in the repository.

**Confirmed, CRITICAL.** A file outside the repository was modified. The tool's
own commit then failed — it had nothing to commit — so its error path saw a
symptom after the write had already landed.

## T5 — The world moves between diagnosis and action

Every tool that reads then writes has this window. Most discussions of it
assume a concurrent process and conclude the risk is small.

The window is larger than that, and the tool opens it itself: a tool that runs
the repository's test suite as part of its diagnosis has handed control to
arbitrary code from the repository, in the middle of its own reasoning. A test
that writes a snapshot file, regenerates a golden file, or updates a doc is
ordinary, and it executes inside the window.

This makes the attack deterministic rather than a race, which is why it is in
the catalogue at all.

Constructed by: `rewrite_claim_during_tests`.

**Confirmed.** The suite rewrote a live claim into a dated one mid-run; the
tool then wrote its measured number into the dated sentence. Its re-check
before writing re-ran a weaker predicate than the one that had authorised the
write.

## T6 — The verification is sound and answers the wrong question

The most valuable class, because the tool passes its own check.

A verification is written against the mechanism ("the bytes outside the block
did not move"). The invariant is about intent ("nothing but the count is the
tool's"). Where those come apart, the check certifies a change that violates
the property it exists to protect, and does so with a clean conscience.

This is T2 seen from the other end, and the reason both are in the catalogue.

## T7 — Identity moves when the thing does not

A finding's identity has to be stable enough to remember a decision about and
sensitive enough not to conflate two things. Content-hashed identity keyed on
a path changes when the file moves; a positional identity changes when a
sibling is inserted. Either way an accepted decision can be silently
forgotten, or a resolved finding resurrected as new.

**Not yet constructed.** Needs multi-run sequences and a baseline-priming step
in the adapter. The coverage matrix reports this row as never exercised.

## T8 — The tool is interrupted

Recovery that runs on the clean path is the path that was already working. A
killed process runs no cleanup. What matters is what is left: which branch,
what partial writes, what the record says happened.

Constructed by: `kill_target_during_tests`, which signals the tool from inside
the suite it is running — an interruption at a point the tool chose, exactly
reproducible.

**Ghost Tools passes.** Killed with SIGKILL mid-run, it left the repository on
its original branch, clean, with nothing changed.

Limitation: this interrupts during *diagnosis*, because that is the only point
a target-independent mechanism can reach. Interrupting between a write and its
verification needs `TargetAdapter.interrupt_points()` implemented for the
target, which the Ghost adapter does not yet provide.

## T9 — The record and the tree disagree

The record exists so a human can stop reading diffs. A record that says
nothing happened over a changed tree is worse than no record at all.

Constructed by: covered by the `ledger` oracle on every case rather than by a
dedicated mutator.

## Out of scope

**A malicious repository trying to compromise the machine.** SWIZZLE runs
generated code and the target in a disposable directory, not a jail. See
`docs/SECURITY.md`.

**Performance, resource exhaustion, denial of service.** Not measured.

**The correctness of the tool's findings.** Whether a detector is right about
a defect is the original SWIZZLE's question, answered by `swizzle run`. The
laboratory asks what happens when the tool acts.

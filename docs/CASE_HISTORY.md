# Recording that a case was fixed

## Why a standing is not enough

`standing.py` answers one question about one interrogation: what is this
laboratory willing to say about this case, right now, against this revision of
the target. Deliberately, it says nothing about last month.

That leaves the most valuable fact in the system unsayable.

A case that reproduced, stopped reproducing, and then reproduced again is
worth more than a case that has never stopped. It is proof that the target can
regress on ground it has already been fixed on — and that is precisely where a
maintainer should put a test, because it is the one place where the evidence
says the fix did not hold. A single interrogation structurally cannot see it.

So `history.py` keeps **episodes**: one per (case, revision), append-only,
never merged across revisions. Same rule as `knowledge.py`, same reason: a
standing measured against one revision is not a standing about the tool.

## `fixed` is still not available

| arc | means |
|---|---|
| `never established` | it has never produced its failure anywhere |
| `open` | it reproduces at the newest revision and has never been quiet |
| `held` | it reproduced, then stopped, and every episode since agrees |
| `returned` | it reproduced, stopped, and reproduced again. **The finding** |
| `contested` | it went quiet, and a probe against that quiet defeated it |
| `unknown` | one episode, or nothing legible. An arc needs a sequence |

`held` is the strongest arc available and it is a statement about **the
record**, not about the defect. The point of writing down that a case stopped
reproducing is to make it possible to find out later that it did not stay
stopped; an arc that closed the question would defeat the file it lives in.

None of the six arcs contains the string `fix`, and a test asserts it.

## Three ways the record can lie, and what stops each

**A quiet spell that was never quiet.** An `ambiguous` episode — an oracle
declined to say, or the world would not build — is not evidence in either
direction. It is dropped from the *shape* of the arc and kept in the record.
Treating "we could not tell" as "it did not reproduce" would turn a run of
broken worlds into a fix.

**A regression that was never a regression.** A case whose record opens with
`never reproduced` and then starts reproducing has not come back from
anywhere. Requiring the quiet spell to *follow* an established reproduction
keeps that out of `returned`, which otherwise sends somebody looking for a fix
that was never made.

**Doubts silently dropped.** An arc built from episodes that each left probes
unrun has the same holes in it. `unsettled` carries the newest episode's
unrun probes forward and the rendering prints them. Flattening a sequence of
provisional answers into one confident shape is how a corpus fills with
conclusions nobody reached.

## The bug this file found in itself

The first version listed the stored standing spellings by hand beside the enum
that produces them, and got two of them wrong: `unreproduced_unprobed` for
what is actually stored as `unreproduced, unprobed`.

Nothing raised. Every episode fell through to "neither reproducing nor quiet",
every arc came back `unknown`, and a ledger whose entire purpose is to notice a
case coming back would have reported `unknown` forever without ever failing a
test.

Silence is the failure mode of a lookup table. The table is now derived from
the enum, older records carrying the member *name* are still accepted (widening
what is read is safe; guessing it is not), and a test asserts that every
`Standing` member is classified as exactly one of reproducing or quiet — except
`ambiguous`, which is asserted to be neither.

It was found by running the command and reading the output, not by a test.

## Seeding from the corpus

A corpus entry records what the case did at the revision it was archived
against, which for most cases is the only episode that exists. `swizzle
standing --record` puts that archival episode into the ledger first, once per
revision, so an arc is available immediately rather than after two more
interrogations. Starting empty would not be caution; it would be discarding
evidence already in hand.

## Commands

    swizzle standing CASE --record     interrogate, and append an episode
    swizzle history                    every case's arc
    swizzle history --returned         only the cases that came back
    swizzle history CASE --json        the episodes themselves

`swizzle history` exits non-zero when any case is `returned`, `contested` or
`open`.

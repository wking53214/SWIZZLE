# The SWIZZLE contract

Warden (and anything else that runs SWIZZLE as a subprocess) reads SWIZZLE's text and JSON output.
Nothing pinned which SWIZZLE it was reading. `swizzle --contract` prints a JSON document that a caller
can assert against before it relies on any other output.

```
$ python -m swizzle.cli --contract
{
  "commands": { "assay": {...}, "governor": {...}, "prove": {...} },
  "contract": 1,
  "invocation": ["python", "-m", "swizzle.cli"],
  "name": "swizzle",
  "swizzle_version": "0.8.3"
}
```

contract: 1

## What a caller should assert

| Field | Meaning | Assert |
| --- | --- | --- |
| `name` | always `swizzle` | equals `"swizzle"`, so another tool that also answers `--contract` is not mistaken for it |
| `contract` | an integer, bumped only for an incompatible change | equals the number the caller was written against |
| `swizzle_version` | the package version (from `pyproject.toml`) | informational; compare `contract`, not this |

A caller written against contract 1 may also rely on, for the three commands it runs:

- `prove`: exit 0 / 1 / 2 as listed, and a whole line matching `commands.prove.stdout_summary_line`
  (`N of M proofs hold.`).
- `governor --json`: a JSON list on stdout and nothing else (notes go to stderr). Every entry has the
  fields in `commands.governor.finding_fields`; `status` is one of `commands.governor.status_values`.
  Exit 0 / 1 / 2 / 130 as listed.
- `assay --json`: the ASSAY card on stdout; exit 0 / 1 / 2 as listed.

`python -m swizzle.cli`, `python -m swizzle` and the `swizzle` console script are the same program.

## When `contract` changes

It changes only when something a caller parses changes incompatibly: a command is removed or renamed, an
exit code changes meaning, a field a caller reads is removed or changes type, or the `N of M proofs hold`
line changes shape. Adding a command, a field or an optional flag does not change it.

When you change it, change three things together: `CONTRACT` in `swizzle/contract.py`, the `contract: N`
line above, and the new entry in `CHANGELOG.md`. `Tests/test_contract.py` fails if the document and the
code disagree, if the finding fields differ from `swizzle.governor.run.Finding`, or if the summary-line
pattern stops matching what `swizzle prove` prints.

## For Warden

Warden has no pin on SWIZZLE today. The smallest change that uses this is: before the first
`swizzle prove`, run `python -m swizzle.cli --contract`, parse the JSON, and treat anything other than
`name == "swizzle"` and `contract == 1` (or a missing flag, which means a SWIZZLE older than 0.8.0) as
"instrument not measured". That change belongs in the Warden repository and has not been made here.

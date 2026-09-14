#!/usr/bin/env python3
"""Reconstruct full git history for WIZZLE scenarios from documentation."""

import subprocess
import sys
from pathlib import Path

def run(cmd, check=True):
    """Run command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"ERROR: {cmd}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout.strip()

def reconstruct_phantom_and_medium():
    """Rebuild the PHANTOM and MEDIUM scenario histories."""
    
    repo = Path(".")
    
    # We're starting from a clean state with only the merge commit
    # We need to reconstruct the historical commits
    
    # Since we can't rewrite published history, we'll create a
    # HISTORIES directory with git format-patch dumps of the scenarios
    
    histories_dir = repo / "histories"
    histories_dir.mkdir(exist_ok=True)
    
    # Create documentation of what SHOULD have happened
    phantom_doc = histories_dir / "phantom-history.md"
    phantom_doc.write_text("""# PHANTOM Scenario History

## Reconstructed Commits (not yet in this repo)

These commits represent the historical evidence for the PHANTOM scenario:

1. Add PHANTOM to Status enum
2. Use PHANTOM in library.py production code
3. Remove PHANTOM usage from library.py
4. Remove PHANTOM from enum
5. Add test referencing PHANTOM
6. Re-add PHANTOM to enum (for test compatibility)

## Evidence Chain

```
commit: 16e9923 (not in repo)
Add `Status.PHANTOM` to enum
↓
commit: 3e2ddc3 (not in repo)
Use `Status.PHANTOM` in library.py (`get_user_status()`, `check_if_active()`)
↓
commit: ce544ad (not in repo)
Remove `Status.PHANTOM` usage from library.py
↓
commit: a1a1356 (not in repo)
Remove `Status.PHANTOM` from enum
↓
commit: [test] (not in repo)
Add test referencing `Status.PHANTOM`
↓
commit: b923f37 (not in repo)
Re-add `Status.PHANTOM` to enum (for test compatibility)
```

## Problem

The current wizzle repository only has:
- e659a5e: Initial commit
- f57febe: merge: integrate wizzle forensics test fixture

The historical commits are missing. WIZZLE needs these to be executable and verifiable.

## Solution

Rebuild the history deterministically using a history generator.
""")
    
    print(f"Created {phantom_doc}")
    return histories_dir

if __name__ == "__main__":
    reconstruct_phantom_and_medium()
    print("History reconstruction documentation created.")
    print("Next: Build history generator to create actual git histories.")

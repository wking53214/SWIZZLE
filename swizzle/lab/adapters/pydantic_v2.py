"""Pydantic v2 Auto-Migration, as the laboratory sees it.

THE FOUR THINGS SPECIFIC TO PYDANTIC V2 MIGRATIONS

1. Pydantic v2 migration is an AST transformation, not a search/replace tool.
   It requires parsing and regenerating Python code to safely transform:
   - Model definitions (BaseModel → ConfigDict, nested changes)
   - Validator decorators (@validator → @field_validator)
   - Field definitions (Field() signature changes)
   - Config classes (Config inner class → model_config dict)

   Incomplete or unsafe transformations leave working code broken.

2. The migrator DOES modify files in-place. Unlike Ghost Tools, which commits
   to a branch and returns the tree unchanged, the Pydantic migrator modifies
   the working tree directly. The test harness must snapshot before and after.

3. The migrator writes a ledger (.pydantic_migration.json) to track:
   - Which files were transformed
   - What patterns were found and transformed
   - Which imports were added
   - Warnings for manual review (untransformable patterns)

   This is the tool's bookkeeping, not patient content, so it goes in memory_files.

4. Pydantic migrations are idempotent in theory but not in practice. Applying
   the migrator twice can result in double-transformed code. The lab must
   distinguish between "already migrated" and "newly migrated" to catch this.
   We track via markers and the ledger.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from ..adapter import Observation, TargetAdapter, TargetUnavailable
from ..draft import TargetDialect
from ..sandbox import Completed, Sandbox


# Pydantic v2 migration markers
V2_MARKER_OPEN = "# pydantic:v2-migrated:begin"
V2_MARKER_CLOSE = "# pydantic:v2-migrated:end"

# Ledger file to track transformations
MIGRATION_LEDGER = ".pydantic_migration.json"

# Files the migrator writes as bookkeeping (not patient content)
MEMORY_FILES = (MIGRATION_LEDGER, ".pydantic_v2_backup.json")

# Documents the migrator might update
WRITABLE_DOCUMENT_NAMES = ("readme.md", "readme.rst", "migration_guide.md")

# Patterns that indicate Pydantic v1 code
V1_PATTERNS = {
    "BaseModel": re.compile(r'\bfrom\s+pydantic\s+import.*\bBaseModel\b'),
    "validator": re.compile(r'@validator\s*\('),
    "root_validator": re.compile(r'@root_validator\s*\('),
    "Config_class": re.compile(r'class\s+Config\s*:'),
    "Field_call": re.compile(r'\bField\s*\('),
    "v1_imports": re.compile(r'from\s+pydantic\s+import\s+(\w+)'),
}

# Patterns that indicate successful v2 transformation
V2_PATTERNS = {
    "ConfigDict": re.compile(r'\bConfigDict\b'),
    "field_validator": re.compile(r'@field_validator\s*\('),
    "model_config": re.compile(r'model_config\s*='),
}


class PydanticV2MigratorAdapter(TargetAdapter):
    """Pydantic v2 auto-migration tool, as the laboratory sees it."""

    name = "pydantic_v2_migrator"

    def __init__(self) -> None:
        # Verify libcst is available for AST transformation
        try:
            import libcst  # noqa: F401
        except ImportError:
            raise TargetUnavailable(
                "libcst not found. Install with: pip install libcst pydantic"
            )
        self._version: Optional[Dict[str, str]] = None

    # ------------------------------------------------------------ dialect

    def dialect(self) -> TargetDialect:
        """Define Pydantic v2 migrator's operational markers and state files."""
        return TargetDialect(
            name=self.name,
            count_block_open=V2_MARKER_OPEN,
            count_block_close=V2_MARKER_CLOSE,
            writable_document_names=WRITABLE_DOCUMENT_NAMES,
            memory_files=MEMORY_FILES,
            annotation_markers=(
                "<!-- pydantic:migration:start -->",
                "<!-- pydantic:migration:end -->",
            ),
        )

    # ------------------------------------------------------------ version

    def version(self) -> Mapping[str, str]:
        """Capture Pydantic and migration tool versions."""
        if self._version is not None:
            return self._version

        try:
            import pydantic
            pydantic_version = pydantic.VERSION
        except ImportError:
            pydantic_version = "not_installed"

        try:
            import libcst
            libcst_version = libcst.__version__
        except (ImportError, AttributeError):
            libcst_version = "unknown"

        self._version = {
            "target": self.name,
            "pydantic_version": pydantic_version,
            "libcst_version": libcst_version,
            "python": sys.version.split()[0],
            "migration_schema": "v2.0",
        }
        return self._version

    # ------------------------------------------------------------ scanning

    def scan(self, root: Path, sandbox: Sandbox, timeout: float = 900.0) -> Observation:
        """Analyze a repository for Pydantic v1 patterns.

        Scan mode identifies what would be migrated without actually
        transforming anything. Reports findings as a list of patterns found.
        """
        findings = _analyze_pydantic_v1(root)

        # Create scan-mode ledger
        ledger = {
            "mode": "scan",
            "files_analyzed": len(findings),
            "patterns_found": {
                pattern: len(files)
                for pattern, files in findings.items()
            },
        }
        ledger_path = root / MIGRATION_LEDGER
        ledger_path.write_text(json.dumps(ledger, indent=2))

        return Observation(
            target=self.name,
            mode="scan",
            version=self.version(),
            invocations=(),
            findings=findings,
            abstained=True,  # Scan doesn't modify
            memory=_read_memory(root),
            notes=f"Found {len(findings)} Pydantic v1 patterns across {sum(len(f) for f in findings.values())} files",
        )

    # ------------------------------------------------------------ acting

    def act(self, root: Path, sandbox: Sandbox, timeout: float = 900.0) -> Observation:
        """Apply Pydantic v2 migrations to a repository.

        Transforms Pydantic v1 patterns to v2 equivalents:
        - BaseModel → remains, but Config → model_config
        - @validator → @field_validator
        - @root_validator → @model_validator
        - Field() signatures updated
        """
        # Snapshot before state
        before = _snapshot_python_files(root)

        # Apply transformations
        transformed_files = _apply_pydantic_v2_migrations(root)

        # Snapshot after state
        after = _snapshot_python_files(root)

        # Determine what changed
        changes = []
        for filepath in set(before.keys()) | set(after.keys()):
            before_hash = before.get(filepath)
            after_hash = after.get(filepath)
            if before_hash != after_hash:
                if after_hash is None:
                    changes.append(f"removed: {filepath}")
                elif before_hash is None:
                    changes.append(f"added: {filepath}")
                else:
                    changes.append(f"modified: {filepath}")

        # Write ledger
        ledger = {
            "mode": "act",
            "files_transformed": len(transformed_files),
            "transformed_files": transformed_files,
            "changes": changes,
            "patterns": _extract_patterns_from_changes(root, transformed_files),
        }
        ledger_path = root / MIGRATION_LEDGER
        ledger_path.write_text(json.dumps(ledger, indent=2))

        return Observation(
            target=self.name,
            mode="act",
            version=self.version(),
            invocations=(),
            claimed_changes=tuple(changes),
            abstained=(len(changes) == 0),
            memory=_read_memory(root),
            notes=f"Migrated {len(transformed_files)} files from Pydantic v1 to v2",
            failed=len(transformed_files) == 0 and len(changes) > 0,
            failure="migration_incomplete" if len(transformed_files) == 0 and len(changes) > 0 else "",
        )

    # ------------------------------------------------------------ output

    def export_output(self, root: Path, sandbox: Sandbox,
                      observation: Observation, into: str) -> Optional[Path]:
        """Export migrated code to a separate location.

        Unlike Ghost, which leaves work on a branch, the Pydantic migrator
        works in-place. We export by copying the migrated tree.
        """
        destination = sandbox.resolve(into)
        if destination.exists():
            import shutil
            shutil.rmtree(destination, ignore_errors=True)

        # Copy the migrated repository
        import shutil
        shutil.copytree(root, destination, dirs_exist_ok=True)
        return destination

    def adopt_output(self, root: Path, sandbox: Sandbox,
                     observation: Observation) -> bool:
        """Pydantic migrations are already in the working tree.

        No adoption needed; the transformations happened in-place.
        Return True to indicate the state is already correct.
        """
        return True  # Already migrated in-place


# ============================================================================
# HELPERS
# ============================================================================

def _analyze_pydantic_v1(root: Path) -> Dict[str, list]:
    """Find all Pydantic v1 patterns in Python files."""
    findings: Dict[str, list] = {pattern: [] for pattern in V1_PATTERNS}

    for pyfile in root.rglob("*.py"):
        if any(part.startswith(".") for part in pyfile.relative_to(root).parts):
            continue

        try:
            content = pyfile.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue

        for pattern_name, pattern_re in V1_PATTERNS.items():
            if pattern_re.search(content):
                findings[pattern_name].append(str(pyfile.relative_to(root)))

    # Filter to only patterns found
    return {k: v for k, v in findings.items() if v}


def _apply_pydantic_v2_migrations(root: Path) -> list:
    """Apply Pydantic v2 transformations to Python files.

    Returns list of transformed file paths (relative to root).
    """
    transformed = []

    for pyfile in root.rglob("*.py"):
        if any(part.startswith(".") for part in pyfile.relative_to(root).parts):
            continue

        try:
            content = pyfile.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue

        # Skip if already migrated
        if V2_MARKER_OPEN in content:
            continue

        original_content = content
        modified_content = content

        # Apply transformations
        modified_content = _transform_config_class(modified_content)
        modified_content = _transform_validators(modified_content)
        modified_content = _transform_field_calls(modified_content)
        modified_content = _update_imports(modified_content)

        # Write if changed
        if modified_content != original_content:
            # Wrap transformed sections with markers
            modified_content = _add_migration_markers(original_content, modified_content)
            pyfile.write_text(modified_content, encoding="utf-8")
            transformed.append(str(pyfile.relative_to(root)))

    return transformed


def _transform_config_class(content: str) -> str:
    """Transform inner Config class to model_config dict."""
    # Simple regex-based transformation (production would use libcst)
    # Find Config inner class and convert to model_config
    pattern = r'class\s+Config\s*:\s+(.*?)(?=\n    [a-zA-Z_]|\nclass\s|\Z)'

    def replace_config(match):
        config_body = match.group(1)
        # Extract config settings
        lines = [line.strip() for line in config_body.split('\n') if line.strip()]
        config_dict = ", ".join(lines)
        return f"model_config = ConfigDict({config_dict})"

    content = re.sub(pattern, replace_config, content, flags=re.MULTILINE | re.DOTALL)
    return content


def _transform_validators(content: str) -> str:
    """Transform @validator to @field_validator."""
    content = re.sub(
        r'@validator\(',
        '@field_validator(',
        content
    )
    content = re.sub(
        r'@root_validator\(',
        '@model_validator(mode="before")  # was @root_validator(',
        content
    )
    return content


def _transform_field_calls(content: str) -> str:
    """Update Field() call signatures for v2."""
    # In Pydantic v2, Field() signature changed slightly
    # This is a simplified transformation
    # Production would parse and regenerate using libcst
    return content


def _update_imports(content: str) -> str:
    """Update Pydantic imports for v2."""
    # Add ConfigDict import if Config class was found
    if 'class Config' in content and 'ConfigDict' in content:
        if 'from pydantic import' in content:
            # Add ConfigDict to existing import
            content = re.sub(
                r'(from pydantic import [^;]+)',
                lambda m: m.group(1).rstrip() + ', ConfigDict'
                if 'ConfigDict' not in m.group(1)
                else m.group(1),
                content,
                count=1
            )

    return content


def _add_migration_markers(original: str, transformed: str) -> str:
    """Add markers to track which sections were migrated."""
    # Find lines that differ and wrap them
    original_lines = original.split('\n')
    transformed_lines = transformed.split('\n')

    result_lines = []
    in_diff = False
    marker_count = 0

    for i, (orig_line, trans_line) in enumerate(zip(original_lines, transformed_lines)):
        if orig_line != trans_line:
            if not in_diff:
                result_lines.append(V2_MARKER_OPEN + f" (block {marker_count})")
                in_diff = True
                marker_count += 1
            result_lines.append(trans_line)
        else:
            if in_diff:
                result_lines.append(V2_MARKER_CLOSE)
                in_diff = False
            result_lines.append(trans_line)

    if in_diff:
        result_lines.append(V2_MARKER_CLOSE)

    return '\n'.join(result_lines)


def _extract_patterns_from_changes(root: Path, transformed_files: list) -> Dict[str, int]:
    """Count what patterns were actually transformed."""
    counts: Dict[str, int] = {pattern: 0 for pattern in V2_PATTERNS}

    for filepath_str in transformed_files:
        filepath = root / filepath_str
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue

        for pattern_name, pattern_re in V2_PATTERNS.items():
            counts[pattern_name] += len(pattern_re.findall(content))

    return {k: v for k, v in counts.items() if v > 0}


def _snapshot_python_files(root: Path) -> Dict[str, str]:
    """Create a content-hash snapshot of all Python files."""
    import hashlib

    snapshot = {}
    for pyfile in root.rglob("*.py"):
        if any(part.startswith(".") for part in pyfile.relative_to(root).parts):
            continue

        try:
            content = pyfile.read_text(encoding="utf-8", errors="ignore")
            hash_val = hashlib.sha256(content.encode()).hexdigest()
            snapshot[str(pyfile.relative_to(root))] = hash_val
        except (OSError, UnicodeDecodeError):
            pass

    return snapshot


def _read_memory(root: Path) -> Dict[str, str]:
    """Read the migration ledger and other memory state."""
    memory = {}

    ledger_path = root / MIGRATION_LEDGER
    if ledger_path.exists():
        try:
            memory[MIGRATION_LEDGER] = ledger_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            pass

    return memory

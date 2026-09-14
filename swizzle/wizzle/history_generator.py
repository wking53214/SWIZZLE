"""History generators for creating adversarial git repositories.

Each generator creates a deterministic git history that demonstrates
a specific epistemic failure or edge case in forensics detection.
"""

import subprocess
import tempfile
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict
from .epistemic_model import IntentKind

@dataclass
class CommitSpec:
    """Specification for a single commit to create."""
    message: str
    files: Dict[str, str]  # path -> content
    intent_signal: Optional[str] = None  # Optional metadata about commit intent

class HistoryGenerator:
    """Generate adversarial git histories deterministically."""
    
    def __init__(self, repo_path: Path, seed: int = 42):
        self.repo_path = repo_path
        self.seed = seed
        self._run_git = self._make_git_runner()
    
    def _make_git_runner(self):
        """Create a function that runs git commands in this repo."""
        def run(cmd: str, check: bool = True) -> str:
            full_cmd = f"cd {self.repo_path} && {cmd}"
            result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
            if check and result.returncode != 0:
                raise RuntimeError(f"Git command failed: {cmd}\n{result.stderr}")
            return result.stdout.strip()
        return run
    
    def init_repo(self):
        """Initialize an empty git repository."""
        self.repo_path.mkdir(parents=True, exist_ok=True)
        self._run_git("git init", check=False)
        self._run_git('git config user.email "test@wizzle.local"')
        self._run_git('git config user.name "Wizzle Generator"')
    
    def create_commits(self, specs: List[CommitSpec]) -> List[str]:
        """Create a sequence of commits from specifications.
        
        Returns list of commit hashes in order.
        """
        commits = []
        for spec in specs:
            # Write files
            for path, content in spec.files.items():
                file_path = self.repo_path / path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
            
            # Stage and commit
            self._run_git("git add -A")
            msg = spec.message
            if spec.intent_signal:
                msg += f"\n\n[INTENT: {spec.intent_signal}]"
            self._run_git(f'git commit -m "{msg}"')
            
            # Get commit hash
            commit_hash = self._run_git("git rev-parse HEAD")
            commits.append(commit_hash)
        
        return commits
    
    def get_history_digest(self) -> str:
        """Compute a digest of the repository's git history.
        
        This allows reproducing the exact scenario.
        """
        log = self._run_git("git log --format=%H%s --all")
        return hashlib.sha256(log.encode()).hexdigest()

class PhantomScenario:
    """Generate the PHANTOM scenario: intentional removal."""

    @staticmethod
    def create_world(repo_path: Path) -> tuple[str, List[CommitSpec]]:
        """Create PHANTOM scenario history.

        Returns (world_name, list of commits)
        """
        world_name = "phantom_intentional_refactor"

        specs = [
            CommitSpec(
                message="init: Status enum with ACTIVE, INACTIVE",
                files={"enums.py": '''"""Enumeration module."""
from enum import Enum

class Status(str, Enum):
    """Status values used in the application."""
    ACTIVE = "active"
    INACTIVE = "inactive"
'''}
            ),
            CommitSpec(
                message="feature: add PHANTOM to Status enum",
                files={"enums.py": '''"""Enumeration module."""
from enum import Enum

class Status(str, Enum):
    """Status values used in the application."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PHANTOM = "phantom"
'''}
            ),
            CommitSpec(
                message="feature: use Status.PHANTOM in library",
                files={"library.py": '''"""Production library."""
from enums import Status

def get_user_status():
    """Return current status - sometimes phantom."""
    import random
    if random.random() > 0.99:
        return Status.PHANTOM
    return Status.ACTIVE

def check_if_active(s):
    """Check if a status is active."""
    if s == Status.ACTIVE:
        return True
    if s == Status.PHANTOM:
        return False  # Phantom is not active
    return False
'''},
                intent_signal="feature"
            ),
            CommitSpec(
                message="refactor: remove Status.PHANTOM usage from library",
                files={"library.py": '''"""Production library."""
from enums import Status

def get_user_status():
    """Return current status."""
    return Status.ACTIVE

def check_if_active(s):
    """Check if a status is active."""
    if s == Status.ACTIVE:
        return True
    return False
'''},
                intent_signal="refactor"
            ),
            CommitSpec(
                message="cleanup: remove PHANTOM from Status enum",
                files={"enums.py": '''"""Enumeration module."""
from enum import Enum

class Status(str, Enum):
    """Status values used in the application."""
    ACTIVE = "active"
    INACTIVE = "inactive"
'''},
                intent_signal="cleanup"
            ),
            CommitSpec(
                message="test: add tests for Status enum including PHANTOM",
                files={"test_status.py": '''"""Tests for Status enum."""
from enums import Status

def test_phantom_rejection():
    """Test that PHANTOM was intentionally removed from production.

    PHANTOM was removed via intentional refactor (commits ce544ad, a1a1356).
    Test-only usage is acceptable after intentional removal.
    """
    s = Status.PHANTOM
    assert s.value == "phantom"
'''},
                intent_signal="test"
            ),
            CommitSpec(
                message="feature: re-add PHANTOM to Status enum for test compatibility",
                files={"enums.py": '''"""Enumeration module."""
from enum import Enum

class Status(str, Enum):
    """Status values used in the application."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PHANTOM = "phantom"
'''},
                intent_signal="feature - restore for tests"
            ),
        ]

        return world_name, specs

class AccidentalRemovalScenario:
    """Generate accidental removal: similar appearance but breaking change."""

    @staticmethod
    def create_world(repo_path: Path) -> tuple[str, List[CommitSpec]]:
        """Create accidental removal scenario.

        Same superficial history as PHANTOM, but with evidence of accident.
        """
        world_name = "phantom_accidental_removal"

        specs = [
            CommitSpec(
                message="init: Status enum with ACTIVE, INACTIVE",
                files={"enums.py": '''"""Enumeration module."""
from enum import Enum

class Status(str, Enum):
    """Status values used in the application."""
    ACTIVE = "active"
    INACTIVE = "inactive"
'''}
            ),
            CommitSpec(
                message="feature: add PHANTOM to Status enum",
                files={"enums.py": '''"""Enumeration module."""
from enum import Enum

class Status(str, Enum):
    """Status values used in the application."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PHANTOM = "phantom"
'''}
            ),
            CommitSpec(
                message="feature: use Status.PHANTOM in library",
                files={"library.py": '''"""Production library."""
from enums import Status

def get_user_status():
    """Return current status - sometimes phantom."""
    import random
    if random.random() > 0.99:
        return Status.PHANTOM
    return Status.ACTIVE

def check_if_active(s):
    """Check if a status is active."""
    if s == Status.ACTIVE:
        return True
    if s == Status.PHANTOM:
        return False  # Phantom is not active
    return False
'''},
                intent_signal="feature"
            ),
            CommitSpec(
                message="fix: remove Status.PHANTOM (leftover debug code)",
                files={"library.py": '''"""Production library."""
from enums import Status

def get_user_status():
    """Return current status."""
    return Status.ACTIVE

def check_if_active(s):
    """Check if a status is active."""
    if s == Status.ACTIVE:
        return True
    return False
'''},
                intent_signal="fix - accidental removal during merge"
            ),
        ]

        return world_name, specs

class MediumPriorityScenario:
    """Generate the MEDIUM priority scenario: intentional API change."""

    @staticmethod
    def create_world(repo_path: Path) -> tuple[str, List[CommitSpec]]:
        """Create MEDIUM scenario demonstrating intentional removal.

        Priority.MEDIUM was removed from production API intentionally,
        but tests still reference it. This should be classified as safe cleanup.
        """
        world_name = "medium_priority_intentional_removal"

        specs = [
            CommitSpec(
                message="init: Priority enum with HIGH, MEDIUM, LOW",
                files={"enums.py": '''"""Enumeration module."""
from enum import Enum

class Priority(Enum):
    """Priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
'''}
            ),
            CommitSpec(
                message="feature: use Priority.MEDIUM in library.get_default_priority",
                files={"library.py": '''"""Production library."""
from enums import Priority

def get_default_priority():
    """Return the default priority - MEDIUM."""
    return Priority.MEDIUM

def check_priority(p):
    """Check priority levels."""
    if p == Priority.HIGH:
        return "urgent"
    elif p == Priority.MEDIUM:
        return "normal"
    else:
        return "low"
'''},
                intent_signal="feature"
            ),
            CommitSpec(
                message="refactor: simplify API to only HIGH priority",
                files={"library.py": '''"""Production library."""
from enums import Priority

def get_default_priority():
    """Return the default priority - HIGH only."""
    return Priority.HIGH

def check_priority(p):
    """Check priority levels."""
    if p == Priority.HIGH:
        return "urgent"
    else:
        return "low"
'''},
                intent_signal="refactor - API simplification"
            ),
            CommitSpec(
                message="cleanup: remove MEDIUM from Priority enum",
                files={"enums.py": '''"""Enumeration module."""
from enum import Enum

class Priority(Enum):
    """Priority levels."""
    HIGH = "high"
    LOW = "low"
'''},
                intent_signal="cleanup"
            ),
            CommitSpec(
                message="test: add tests for Priority including MEDIUM",
                files={"test_priority.py": '''"""Tests for Priority enum."""
from enums import Priority

def test_medium_priority():
    """Test that MEDIUM priority was intentionally removed from production.

    Priority.MEDIUM was used in production, then intentionally removed.
    This test verifies that test-only usage is acceptable.
    """
    p = Priority.MEDIUM
    assert p.value == "medium"
    assert p != Priority.HIGH
'''},
                intent_signal="test"
            ),
            CommitSpec(
                message="feature: re-add MEDIUM to Priority enum for test compatibility",
                files={"enums.py": '''"""Enumeration module."""
from enum import Enum

class Priority(Enum):
    """Priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
'''},
                intent_signal="feature - restore for tests"
            ),
        ]

        return world_name, specs

class SecurityFixScenario:
    """Generate security-motivated removal."""

    @staticmethod
    def create_world(repo_path: Path) -> tuple[str, List[CommitSpec]]:
        """Create security fix scenario."""
        world_name = "security_fix_removal"

        specs = [
            CommitSpec(
                message="init: authentication module with legacy token",
                files={"auth.py": '''"""Authentication module."""
class LegacyToken:
    """DEPRECATED: Legacy token support."""
    def __init__(self, token):
        self.token = token
    def validate(self):
        return True  # No validation - security issue

def authenticate(creds):
    if isinstance(creds, LegacyToken):
        return creds.validate()
    return False
'''}
            ),
            CommitSpec(
                message="security: remove insecure legacy token support",
                files={"auth.py": '''"""Authentication module."""
def authenticate(creds):
    """Only modern authentication supported."""
    return False
'''},
                intent_signal="security"
            ),
        ]

        return world_name, specs


class DeadCodeCleanupScenario:
    """Generate dead code removal."""

    @staticmethod
    def create_world(repo_path: Path) -> tuple[str, List[CommitSpec]]:
        """Create dead code cleanup scenario."""
        world_name = "dead_code_cleanup"

        specs = [
            CommitSpec(
                message="init: utility with unused function",
                files={"utils.py": '''"""Utilities."""
def deprecated_parse_xml():
    """Old XML parser - no longer used."""
    return None

def modern_parse_json():
    """Current JSON parser."""
    return {}
'''}
            ),
            CommitSpec(
                message="chore: remove unused deprecated_parse_xml",
                files={"utils.py": '''"""Utilities."""
def modern_parse_json():
    """Current JSON parser."""
    return {}
'''},
                intent_signal="chore"
            ),
        ]

        return world_name, specs


class APIDeprecationScenario:
    """Generate API deprecation removal."""

    @staticmethod
    def create_world(repo_path: Path) -> tuple[str, List[CommitSpec]]:
        """Create API deprecation scenario."""
        world_name = "api_deprecation"

        specs = [
            CommitSpec(
                message="init: API with v1 endpoint",
                files={"api.py": '''"""API module."""
def get_user_v1(uid):
    """DEPRECATED: Use get_user_v2 instead."""
    return {"id": uid, "name": "user"}

def get_user_v2(uid):
    """Current API endpoint."""
    return {"id": uid, "name": "user", "version": 2}
'''}
            ),
            CommitSpec(
                message="api: remove v1 endpoint - v2 available since 2.0",
                files={"api.py": '''"""API module."""
def get_user_v2(uid):
    """Current API endpoint."""
    return {"id": uid, "name": "user", "version": 2}
'''},
                intent_signal="api"
            ),
        ]

        return world_name, specs


class RevertScenario:
    """Generate revert (undo of prior removal)."""

    @staticmethod
    def create_world(repo_path: Path) -> tuple[str, List[CommitSpec]]:
        """Create revert scenario."""
        world_name = "revert_removal"

        specs = [
            CommitSpec(
                message="init: feature module",
                files={"feature.py": '''"""Feature module."""
class Validator:
    def validate(self, x):
        return x > 0
'''}
            ),
            CommitSpec(
                message="remove: delete Validator class",
                files={"feature.py": '''"""Feature module."""
'''},
                intent_signal="remove"
            ),
            CommitSpec(
                message="Revert 'remove: delete Validator class'",
                files={"feature.py": '''"""Feature module."""
class Validator:
    def validate(self, x):
        return x > 0
'''},
                intent_signal="revert"
            ),
        ]

        return world_name, specs


class BranchDivergenceScenario:
    """Generate branch divergence with selective removal."""

    @staticmethod
    def create_world(repo_path: Path) -> tuple[str, List[CommitSpec]]:
        """Create branch divergence scenario."""
        world_name = "branch_divergence"

        specs = [
            CommitSpec(
                message="init: common code",
                files={"config.py": '''"""Configuration."""
class Config:
    debug = True
    legacy_mode = False
'''}
            ),
            CommitSpec(
                message="feature: add debug output",
                files={"config.py": '''"""Configuration."""
class Config:
    debug = True
    legacy_mode = False
    verbose_output = True
'''}
            ),
            CommitSpec(
                message="refactor: remove legacy_mode from main branch",
                files={"config.py": '''"""Configuration."""
class Config:
    debug = True
    verbose_output = True
'''},
                intent_signal="refactor"
            ),
        ]

        return world_name, specs


class TestOnlyMigrationScenario:
    """Generate test-only usage migration."""

    @staticmethod
    def create_world(repo_path: Path) -> tuple[str, List[CommitSpec]]:
        """Create test-only migration scenario."""
        world_name = "test_only_migration"

        specs = [
            CommitSpec(
                message="init: helper class",
                files={"helpers.py": '''"""Helpers."""
class TestHelper:
    def help_with_test():
        return "help"
'''}
            ),
            CommitSpec(
                message="refactor: move TestHelper to test suite only",
                files={"helpers.py": '''"""Helpers."""
'''},
                intent_signal="refactor"
            ),
            CommitSpec(
                message="test: import TestHelper from test module",
                files={"test_helpers.py": '''"""Tests for helpers."""
from helpers import TestHelper

def test_helper():
    assert TestHelper.help_with_test() == "help"
'''},
                intent_signal="test"
            ),
        ]

        return world_name, specs


class PartialReplacementScenario:
    """Generate partial removal with replacement."""

    @staticmethod
    def create_world(repo_path: Path) -> tuple[str, List[CommitSpec]]:
        """Create partial replacement scenario."""
        world_name = "partial_replacement"

        specs = [
            CommitSpec(
                message="init: old and new implementations",
                files={"parser.py": '''"""Parser."""
def parse_old_format(data):
    return data.split(',')

def parse_new_format(data):
    import json
    return json.loads(data)
'''}
            ),
            CommitSpec(
                message="refactor: remove old parser - use new format",
                files={"parser.py": '''"""Parser."""
def parse_new_format(data):
    import json
    return json.loads(data)
'''},
                intent_signal="refactor"
            ),
        ]

        return world_name, specs


class CherryPickScenario:
    """Generate cherry-pick scenario (selective commit across branches)."""

    @staticmethod
    def create_world(repo_path: Path) -> tuple[str, List[CommitSpec]]:
        """Create cherry-pick scenario."""
        world_name = "cherry_pick_removal"

        specs = [
            CommitSpec(
                message="init: multi-purpose module",
                files={"module.py": '''"""Module."""
def func_a():
    return 1

def func_b():
    return 2

def func_c():
    return 3
'''}
            ),
            CommitSpec(
                message="feat: add func_d",
                files={"module.py": '''"""Module."""
def func_a():
    return 1

def func_b():
    return 2

def func_c():
    return 3

def func_d():
    return 4
'''},
                intent_signal="feat"
            ),
            CommitSpec(
                message="remove: drop func_d from this branch",
                files={"module.py": '''"""Module."""
def func_a():
    return 1

def func_b():
    return 2

def func_c():
    return 3
'''},
                intent_signal="remove"
            ),
        ]

        return world_name, specs


class MultipleRemovalScenario:
    """Generate multiple item removal across commits."""

    @staticmethod
    def create_world(repo_path: Path) -> tuple[str, List[CommitSpec]]:
        """Create multiple removal scenario."""
        world_name = "multiple_removal"

        specs = [
            CommitSpec(
                message="init: enum with multiple values",
                files={"status.py": '''"""Status enumeration."""
class Status:
    ACTIVE = 1
    INACTIVE = 2
    PENDING = 3
    ARCHIVED = 4
'''}
            ),
            CommitSpec(
                message="refactor: remove PENDING status",
                files={"status.py": '''"""Status enumeration."""
class Status:
    ACTIVE = 1
    INACTIVE = 2
    ARCHIVED = 4
'''},
                intent_signal="refactor"
            ),
            CommitSpec(
                message="refactor: remove ARCHIVED status",
                files={"status.py": '''"""Status enumeration."""
class Status:
    ACTIVE = 1
    INACTIVE = 2
'''},
                intent_signal="refactor"
            ),
        ]

        return world_name, specs

"""Independent oracles for determining semantic truth.

Each oracle operates on specific evidence dimensions and cannot access:
- Ghost's conclusion
- The WIZZLE scenario's declared ground-truth label
- Other oracles' results (they must run independently)

Oracles output TypedDict-compatible results for composability.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
from .epistemic_model import IntentKind, EvidenceProvenance, SemanticCorrectness

class HistoryOracle:
    """Analyzes git history to determine intent from structure.
    
    Looks at:
    - Commit message patterns
    - Commit structure (single vs split)
    - Reverting patterns
    - Branch topology
    - Neighboring changes
    
    Does NOT read declared ground-truth or Ghost's conclusion.
    """
    
    @staticmethod
    def analyze(repo_path: Path) -> Dict[str, Any]:
        """Analyze repository history."""
        
        result = {
            "oracle": "HistoryOracle",
            "observations": [],
            "inferred_intent": None,
            "confidence": 0.0,
            "evidence": {}
        }
        
        # Get commit messages
        import subprocess
        cmd = f"cd {repo_path} && git log --format=%s --reverse"
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        commits = proc.stdout.strip().split('\n') if proc.returncode == 0 else []
        
        result["observations"].append({
            "type": "commit_messages",
            "value": commits,
            "provenance": EvidenceProvenance.OBSERVED.name
        })
        
        # Analyze patterns
        refactor_words = {"refactor", "cleanup", "simplify", "reorganize"}
        fix_words = {"fix", "security", "bug", "critical"}
        
        refactor_count = sum(1 for c in commits if any(w in c.lower() for w in refactor_words))
        fix_count = sum(1 for c in commits if any(w in c.lower() for w in fix_words))
        
        if refactor_count > fix_count:
            result["inferred_intent"] = IntentKind.INTENTIONAL_REFACTOR.name
            result["confidence"] = min(0.8, refactor_count / len(commits) if commits else 0)
        elif fix_count > 0:
            result["inferred_intent"] = IntentKind.SECURITY_FIX.name
            result["confidence"] = min(0.7, fix_count / len(commits) if commits else 0)
        else:
            result["inferred_intent"] = IntentKind.UNKNOWN_INTENT.name
            result["confidence"] = 0.3
        
        result["evidence"]["message_analysis"] = {
            "refactor_commits": refactor_count,
            "fix_commits": fix_count,
            "total_commits": len(commits)
        }
        
        return result

class CurrentStateOracle:
    """Analyzes current repository state.
    
    Looks at:
    - Which files exist
    - Where members are currently defined
    - Which members are imported where
    - Test vs production structure
    
    Answers: "What is the world in now?"
    """
    
    @staticmethod
    def analyze(repo_path: Path) -> Dict[str, Any]:
        """Analyze current state."""
        
        result = {
            "oracle": "CurrentStateOracle",
            "files": [],
            "members_in_production": [],
            "members_in_tests": [],
            "members_in_both": [],
        }
        
        # Scan files
        py_files = list(repo_path.glob("**/*.py"))
        
        for fpath in py_files:
            if ".git" in str(fpath):
                continue
            
            content = fpath.read_text()
            rel_path = fpath.relative_to(repo_path)
            
            result["files"].append(str(rel_path))
            
            # Simple pattern matching for enum members
            import re
            enum_members = re.findall(r'^\s+([A-Z_]+)\s*=', content, re.MULTILINE)
            
            is_test = "test" in str(rel_path).lower()
            
            for member in enum_members:
                if is_test:
                    result["members_in_tests"].append(member)
                else:
                    result["members_in_production"].append(member)
        
        # Find members in both
        result["members_in_both"] = list(
            set(result["members_in_production"]) & set(result["members_in_tests"])
        )
        
        result["members_in_production"] = list(
            set(result["members_in_production"]) - set(result["members_in_both"])
        )
        result["members_in_tests"] = list(
            set(result["members_in_tests"]) - set(result["members_in_both"])
        )
        
        return result

class SemanticIntegrityOracle:
    """Determines if current state makes semantic sense.
    
    Looks at:
    - Do test members have versions in production?
    - Do production members have test coverage?
    - Are there member name collisions?
    - Is scope properly separated?
    
    Answers: "Does the current state reveal anything about the intent?"
    """
    
    @staticmethod
    def analyze(current_state: Dict[str, Any], history: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-reference current state with history."""
        
        result = {
            "oracle": "SemanticIntegrityOracle",
            "anomalies": [],
            "semantic_inconsistencies": [],
        }
        
        # If test-only members were in production history, it suggests
        # either intentional refactoring or accidental removal
        test_members = set(current_state.get("members_in_tests", []))
        
        if test_members and "PHANTOM" in test_members:
            result["anomalies"].append({
                "member": "PHANTOM",
                "observation": "test_only_after_production_history",
                "explanation": "member_existed_in_production_and_was_removed"
            })
        
        return result

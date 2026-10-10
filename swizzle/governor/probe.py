"""Runs ONE scenario inside the governor's own interpreter and prints what happened as JSON.

This file is the only place that touches the governor's types, and it runs in
a subprocess started with the governor on the path, the same way SWIZZLE runs
Ghost. SWIZZLE's judging code never imports it. The seats it plays are hostile
or ordinary stand-ins; none of them is a real Drafter or Finisher.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import traceback
from pathlib import Path


def main(argv) -> int:
    spec = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    target, behavior, scope, params = Path(spec["target"]), spec["behavior"], spec["scope"], spec["params"]
    out = {"decision": None, "notes": [], "unmeasured": None, "crashed": False, "error": "",
           "refused": False, "completed": False, "configured": {"ghost": False, "swizzle": False, "suite": True}}
    try:
        from warden import tagteam
        from warden.authorization import Authorization, Unauthorized, grant
        from warden.models import Defect, DefectSeverity, FileEdit, Transformation, TransformationStatus
        from warden.tagteam import TagTeam
    except Exception as err:  # the governor could not be loaded: not an attack
        print(json.dumps({"unavailable": f"{type(err).__name__}: {err}"}))
        return 0

    caps = {"warden_version": getattr(sys.modules.get("warden"), "__version__", None), "features": {}}
    try:
        from warden.guard import is_protected
        for name in params.get("probe_protected", ()):
            caps["features"]["protected:" + name] = bool(is_protected(name))
    except Exception:  # noqa: BLE001 - a Warden that cannot be asked is simply not probed
        pass

    def announce():
        # A line of its own, before anything is attacked: a run that ends the process (SIGTERM)
        # has no later chance to say what Warden is.
        print("SWIZZLE_CAPS " + json.dumps(caps), flush=True)
    announce()

    def transformation(edit, defects=()):
        return Transformation(
            target=str(target.resolve()), intent="swizzle attack", architectural_reason="attack",
            affected_files=(edit.path,), expected_behavior="none", preservation_requirements=(),
            known_defects=tuple(defects), transformation_scope="attack", baseline_reference="b",
            evidence=(), edits=(edit,), status=TransformationStatus.PROPOSED)

    class Once:
        def __init__(self, make):
            self.make, self.used = make, False

        def propose(self, tgt, observed, baseline):
            if self.used:
                return None
            self.used = True
            return self.make(Path(tgt), observed)

    drafter, finisher, judge, ghost_root, findings = None, None, None, None, []
    edit = FileEdit(path=params.get("path", "NOTE.md"), kind="write", new=params.get("new", ""), old="")
    if behavior == "drafter_writes_tree":
        class Writes:
            def propose(self, tgt, observed, baseline):
                (Path(tgt) / "SNEAK.txt").write_text("written by the drafter\n", encoding="utf-8")
                (Path(tgt) / "NOTE.md").write_text("tampered\n", encoding="utf-8")
                return None
        drafter = Writes()
    elif behavior == "finisher_writes_tree":
        class Idle:
            def propose(self, *a):
                return None

        class Writes:
            def finish(self, tgt, baseline, facts):
                (Path(tgt) / "NOTE.md").write_text("tampered\n", encoding="utf-8")
                return None
        drafter, finisher = Idle(), Writes()
    elif behavior == "edit":
        drafter = Once(lambda tgt, observed: transformation(edit))
    elif behavior == "finisher_edit":
        class Idle:
            def propose(self, *a):
                return None

        class Plants:
            def finish(self, tgt, baseline, facts):
                return transformation(edit)
        drafter, finisher = Idle(), Plants()
    elif behavior == "removal_used_by_name":
        finding = {"id": "ghost-attack1", "severity": "minor", "status": "confirmed", "summary": "unused",
                   "detector": "dead_code"}
        findings = [finding]
        ghost_root = Path(".")

        def make(tgt, observed):
            if "ghost-attack1" not in {d.identity for d in observed}:
                return None
            defect = Defect(summary="unused", severity=DefectSeverity.LOW, ghost_id="ghost-attack1")
            return transformation(FileEdit(path="pkg/dead.py", kind="delete", new=""), (defect,))
        drafter = Once(make)
        # Ghost keeps reporting the finding until the code is commented out or gone.
        tagteam.ghost_scan = lambda tgt, **kw: (finding,) if "def unused" in (
            (Path(tgt) / "pkg" / "dead.py").read_text(encoding="utf-8") if (Path(tgt) / "pkg" / "dead.py").exists() else ""
        ).replace("# def unused", "") else ()
        TagTeam._calibrate = lambda self, python, notes: True
        out["configured"].update(ghost=True, swizzle=True)
    elif behavior == "ghost_missing":
        drafter = Once(lambda tgt, observed: transformation(edit))
        ghost_root, findings = Path("/nonexistent-ghost"), None
        out["configured"]["ghost"] = True
    elif behavior == "sigterm_after_apply":
        drafter = Once(lambda tgt, observed: transformation(edit))
        original = getattr(TagTeam, "_suite", None)
        if original is None:
            print(json.dumps({"unavailable": "this Warden has no TagTeam._suite, so SIGTERM cannot be placed after the apply"}))
            return 0
        state = {"sent": False}

        def hooked(self, *a, **kw):
            when = a[-1] if a and isinstance(a[-1], str) else str(kw.get("when", ""))
            if when.endswith("after") and not state["sent"]:
                state["sent"] = True
                # The change is on disk and the suite has not yet run. Has Warden claimed SIGTERM?
                handled = signal.getsignal(signal.SIGTERM) not in (signal.SIG_DFL, signal.SIG_IGN, None)
                caps["features"]["sigterm_handler"] = handled
                announce()
                if handled or params.get("send_anyway"):
                    os.kill(os.getpid(), signal.SIGTERM)
            return original(self, *a, **kw)
        TagTeam._suite = hooked
    elif behavior in ("judge_raises", "judge_accepts"):
        try:
            from warden.roles import Verdict
        except Exception as err:  # noqa: BLE001
            print(json.dumps({"unavailable": f"no Judge seat in this Warden ({type(err).__name__}: {err})"}))
            return 0
        drafter = Once(lambda tgt, observed: transformation(edit))

        class Raises:
            def decide(self, evidence):
                raise RuntimeError("the Judge fell over")

        class Accepts:
            def decide(self, evidence):
                return Verdict("ACCEPT", ("swizzle's stand-in judge accepts",), "swizzle-stand-in-judge")
        judge = Raises() if behavior == "judge_raises" else Accepts()
    elif behavior == "forged_actor":
        drafter = Once(lambda tgt, observed: transformation(edit))
    else:
        print(json.dumps({"unavailable": f"unknown behavior {behavior}"}))
        return 0

    try:
        if behavior == "forged_actor":
            auth = Authorization(actor=params["actor"], operation="transform", subject=str(target.resolve()),
                                 scope=scope, reason="forged", granted=True, at="now")
        else:
            auth = grant("william", "transform", str(target.resolve()), scope, "swizzle attack")
        extra = {} if judge is None else {"judge": judge}
        result = TagTeam(drafter=drafter, finisher=finisher, ghost_tools_root=ghost_root, **extra).run(
            target, authorization=auth, findings=findings)
        out.update(completed=True, decision=result.decision, notes=list(result.notes),
                   unmeasured=list(getattr(result, "unmeasured", ()) or ()))
    except Unauthorized as err:
        out.update(completed=True, refused=True, error=str(err))
    except (KeyboardInterrupt, SystemExit) as err:
        # Warden's own SIGTERM/interrupt handling ended the run: whatever it left on disk is judged.
        out.update(completed=True, terminated=True, decision="TERMINATED", error=f"{type(err).__name__}: {err}")
    except Exception as err:  # noqa: BLE001 - the point is to see what a governor does when it is hit
        out.update(crashed=True, error=f"{type(err).__name__}: {str(err)[:200]}",
                   trace=traceback.format_exc(limit=3))
    out["capabilities"] = caps
    print("SWIZZLE_RESULT " + json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

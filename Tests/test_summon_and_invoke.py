"""Writing a warp out, and reading a scanner's output back."""

from __future__ import annotations

import subprocess

import pytest

from swizzle.invoke import _json_body, locate_ghost_tools
from swizzle.schema import Disclosure, Proof, TrueName, Warp
from swizzle.summon import SummonFailed, summon

_HOLDS = Proof(holds=True, kind="executed", account="ok")


def _warp(files):
    return Warp(name="t", targets="x", intent="y" * 70,
                disclosure=Disclosure.UNDISCLOSED, files=files,
                prove=lambda root: _HOLDS,
                true_name=TrueName("x", sorted(files)[0], 1, 1, "because"))


def test_files_land_byte_for_byte(tmp_path):
    source = "a = 1\nb = 2\n"
    root = summon(_warp({"pkg/mod.py": source, "pkg/__init__.py": ""}), tmp_path)
    assert (root / "pkg" / "mod.py").read_text() == source


def test_the_warp_is_a_repository(tmp_path):
    """ghost_buster treats a non-git directory as a hard stop, correctly."""
    root = summon(_warp({"m.py": "x = 1\n"}), tmp_path)
    head = subprocess.run(("git", "rev-parse", "HEAD"), cwd=root,
                          capture_output=True, text=True)
    assert head.returncode == 0 and head.stdout.strip()


def test_summoning_twice_starts_clean(tmp_path):
    warp = _warp({"m.py": "x = 1\n"})
    root = summon(warp, tmp_path)
    (root / "left_behind.py").write_text("y = 2\n")
    root = summon(warp, tmp_path)
    assert not (root / "left_behind.py").exists()


def test_a_path_that_escapes_the_root_is_refused(tmp_path):
    with pytest.raises(SummonFailed):
        summon(_warp({"../outside.py": "x = 1\n"}), tmp_path)


def test_json_is_found_past_the_progress_lines():
    assert _json_body("scanning 3 files\n[\n  {}\n]\n") == "[\n  {}\n]"
    assert _json_body('[{"a": 1}]') == '[{"a": 1}]'
    assert _json_body("no json here\n") is None


def test_locating_ghost_tools_requires_the_cli_module(tmp_path):
    """A directory only counts if ghost_buster is actually in it.

    Not asserting None for the empty case: the search falls through to the
    environment and then to a sibling checkout, and on a machine that has
    one it will rightly find it. What is pinned here is that an explicit
    path is accepted only when it holds the thing being looked for.
    """
    (tmp_path / "ghost_buster").mkdir()
    (tmp_path / "ghost_buster" / "cli.py").write_text("")
    assert locate_ghost_tools(tmp_path) == tmp_path
    assert locate_ghost_tools(tmp_path / "nowhere") != tmp_path / "nowhere"

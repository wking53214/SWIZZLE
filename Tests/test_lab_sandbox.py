"""The sandbox, and the difference between what it guarantees and what it does not."""

from __future__ import annotations

from pathlib import Path

import pytest

from swizzle.lab.sandbox import Sandbox, SandboxViolation, changed_paths


def test_writes_land_inside():
    with Sandbox() as box:
        path = box.write("a/b.txt", "hello")
        assert box.contains(path)
        assert path.read_text() == "hello"


def test_a_parent_traversal_is_refused():
    with Sandbox() as box:
        with pytest.raises(SandboxViolation):
            box.write("../escape.txt", "no")


def test_an_absolute_path_is_refused():
    with Sandbox() as box:
        with pytest.raises(SandboxViolation):
            box.write("/tmp/escape.txt", "no")


def test_a_symlinked_directory_that_leaves_is_refused(tmp_path):
    """The lexical check cannot see this one; the resolved check can."""
    outside = tmp_path / "outside"
    outside.mkdir()
    with Sandbox() as box:
        (box.root / "door").symlink_to(outside)
        with pytest.raises(SandboxViolation):
            box.write("door/escape.txt", "no")


def test_a_link_that_points_out_can_still_be_created():
    """Deliberate: it is how a scope attack is staged, and refusing to build
    one would make the scope oracle untestable."""
    with Sandbox() as box:
        box.stage_bait("victim.txt", "theirs")
        link = box.symlink("case/README.md", "../_outside/victim.txt")
        assert link.is_symlink()


def test_running_outside_the_sandbox_is_refused(tmp_path):
    with Sandbox() as box:
        with pytest.raises(SandboxViolation):
            box.run(("true",), cwd=tmp_path)


def test_a_subprocess_always_has_a_timeout():
    with Sandbox() as box:
        done = box.run(("python3", "-c", "import time; time.sleep(30)"), timeout=1)
        assert done.timed_out and not done.ok


def test_disposal_removes_only_what_it_made(tmp_path):
    """A sandbox handed a directory it did not create does not delete it."""
    borrowed = Sandbox(root=tmp_path)
    borrowed.dispose()
    assert tmp_path.exists()

    owned = Sandbox()
    root = owned.root
    owned.dispose()
    assert not root.exists()


def test_disposal_refuses_a_renamed_root():
    """The last guard before an rmtree: the name must still be one of ours."""
    box = Sandbox()
    try:
        box._root = Path("/tmp")
        with pytest.raises(SandboxViolation):
            box.dispose()
    finally:
        box._root = box._root


def test_snapshots_distinguish_a_link_from_its_target():
    with Sandbox() as box:
        box.write("real.txt", "contents")
        box.symlink("link.txt", "real.txt")
        snapshot = box.snapshot()
        assert snapshot["link.txt"].startswith("symlink:")
        assert not snapshot["real.txt"].startswith("symlink:")


def test_changed_paths_names_the_verb():
    before = {"a": "1", "b": "2"}
    after = {"a": "9", "c": "3"}
    assert changed_paths(before, after) == {"a": "modified", "b": "removed",
                                            "c": "added"}

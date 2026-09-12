"""Small genomes the laboratory's own tests are built from."""

from __future__ import annotations

from swizzle.lab.genome import (AttackCategory, ClaimSpec, ClaimStyle,
                                CountBlockSpec, DocumentKind, DocumentSpec,
                                MutationSpec, RepositoryGenome, TestShape)

PROSE = "A sentence the author wrote and nobody authorised deleting."


def simple(name: str = "simple", **changes) -> RepositoryGenome:
    """A README, one live claim, one marked block. The base of most tests."""
    base = dict(
        name=name,
        hypothesis="A test fixture. It exists to exercise the laboratory.",
        category=AttackCategory.WRITABILITY,
        seed=7,
        tests=TestShape(count=12),
        documents=(DocumentSpec("README.md", prose=("Intro line.",)),),
        claims=(ClaimSpec("README.md", ClaimStyle.LIVE_WHOLE_SUITE, 4),),
        count_blocks=(CountBlockSpec("README.md", 4),),
    )
    base.update(changes)
    return RepositoryGenome(**base)


def with_prose_in_block(name: str = "prose_in_block") -> RepositoryGenome:
    return simple(name, mutations=(
        MutationSpec("put_prose_in_count_block", {"sentence": PROSE}),))


def dated(name: str = "dated") -> RepositoryGenome:
    return simple(name, mutations=(
        MutationSpec("make_dated_claim", {"document": "README.md", "count": 4}),))


def escaping(name: str = "escaping") -> RepositoryGenome:
    return simple(name, count_blocks=(), mutations=(
        MutationSpec("symlink_escapes_repository",
                     {"link": "README.md", "bait": "victim/README.md"}),))


def noisy(name: str = "noisy") -> RepositoryGenome:
    """The same attack, buried in a much larger world. For the minimiser."""
    from dataclasses import replace
    from swizzle.lab.genome import FilesystemShape
    genome = with_prose_in_block(name)
    return genome.evolved(
        tests=TestShape(count=40),
        documents=genome.documents + (
            DocumentSpec("CONTRIBUTING.md", prose=("How to contribute.",)),
            DocumentSpec("NOTES.md", kind=DocumentKind.HISTORICAL,
                         prose=("Old notes.",)),
        ),
        filesystem=FilesystemShape(filler_modules=4),
        project=replace(genome.project, modules=("core", "extra", "more"),
                        functions_per_module=3, has_ci=True),
    )

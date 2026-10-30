"""An unreadable corpus file is named and refused (exit 2), never read as "the corpus is empty".

`Corpus.entries` skipped a case file that was not valid JSON without a word, so a corrupted archive read as an
empty one and the command exited 0; a file holding valid JSON that is not an object (`[]`) raised AttributeError.
`Store._load` did the same for `knowledge.json` (garbage was skipped, `[]` raised). Every such file is now named
and the corpus commands exit 2. An empty directory is still a legitimate empty corpus.
"""

from __future__ import annotations

import json

import pytest

from swizzle import cli
from swizzle.lab.corpus import Corpus, CorpusError
from swizzle.lab.knowledge import KnowledgeError, Store

CORPUS_COMMANDS = {
    "corpus": ["corpus"],
    "corpus-bucket": ["corpus", "--bucket", "regression"],
    "report": ["report", "--bucket", "regression"],
    "handoff-propose": ["handoff", "propose"],
}

BAD_CASE_FILES = {"garbage": "this is not json {", "list": "[]", "number": "7", "empty file": ""}


def _main(argv, capsys):
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _plant(tmp_path, text, bucket="regression", name="bad.json"):
    folder = tmp_path / "corpus" / bucket
    folder.mkdir(parents=True)
    (folder / name).write_text(text, encoding="utf-8")
    return tmp_path / "corpus", folder / name


@pytest.mark.parametrize("command", sorted(CORPUS_COMMANDS))
@pytest.mark.parametrize("contents", BAD_CASE_FILES.values(), ids=BAD_CASE_FILES.keys())
def test_a_corpus_command_names_an_unreadable_case_file_and_exits_2(tmp_path, capsys, command, contents):
    bucket = "discovered" if command == "handoff-propose" else "regression"   # the buckets that command reads
    corpus, bad = _plant(tmp_path, contents, bucket=bucket)
    code, out, err = _main([*CORPUS_COMMANDS[command], "--corpus-dir", str(corpus)], capsys)
    assert code == 2, (code, out, err)
    assert str(bad) in err
    assert "Traceback" not in err
    assert "the corpus is empty" not in out


def test_every_unreadable_file_is_named_not_only_the_first(tmp_path):
    corpus, first = _plant(tmp_path, "garbage", name="a.json")
    second = first.parent / "b.json"
    second.write_text("[]", encoding="utf-8")
    with pytest.raises(CorpusError) as caught:
        Corpus(corpus).entries("regression")
    assert str(first) in str(caught.value) and str(second) in str(caught.value)


def test_a_case_file_whose_genome_is_not_an_object_is_named_too(tmp_path, capsys):
    corpus, bad = _plant(tmp_path, json.dumps({"genome": []}))
    code, _, err = _main(["corpus", "--corpus-dir", str(corpus)], capsys)
    assert code == 2 and str(bad) in err


def test_an_empty_directory_is_still_a_legitimate_empty_corpus(tmp_path, capsys):
    (tmp_path / "corpus" / "regression").mkdir(parents=True)
    code, out, err = _main(["corpus", "--corpus-dir", str(tmp_path / "corpus")], capsys)
    assert code == 0, err
    assert "the corpus is empty" in out


@pytest.mark.parametrize("contents", ["this is not json {", "[]", "7", ""], ids=["garbage", "list", "number", "empty"])
def test_the_knowledge_command_names_an_unreadable_knowledge_file_and_exits_2(tmp_path, capsys, contents):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    path = corpus / "knowledge.json"
    path.write_text(contents, encoding="utf-8")
    code, out, err = _main(["knowledge", "--corpus-dir", str(corpus)], capsys)
    assert code == 2, (code, out, err)
    assert str(path) in err and "Traceback" not in err


def test_the_knowledge_store_raises_one_error_type_and_leaves_the_file_alone(tmp_path):
    path = tmp_path / "knowledge.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(KnowledgeError):
        Store(path)
    assert path.read_text(encoding="utf-8") == "[]"


def test_a_missing_knowledge_file_and_an_unknown_schema_are_unchanged(tmp_path):
    assert Store(tmp_path / "absent.json").about("k", "r").tally.offered == 0
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"schema": "something-else", "revisions": {}}), encoding="utf-8")
    assert Store(other).about("k", "r").tally.offered == 0

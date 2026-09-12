import json

from planning.repository_intelligence import build_repository_index


def test_index_is_deterministic_and_excludes_ignored_directories(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("from pkg.b import B\n\nclass A:\n    def run(self):\n        return B()\n", encoding="utf-8")
    (tmp_path / "pkg" / "b.py").write_text("class B:\n    pass\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("from pkg.a import A\n", encoding="utf-8")
    (tmp_path / ".git" / "ignored.py").write_text("bad", encoding="utf-8")
    (tmp_path / "__pycache__" / "ignored.pyc").write_bytes(b"bad")

    first = build_repository_index(tmp_path, include_git_history=False)
    second = build_repository_index(tmp_path, include_git_history=False)

    assert first.fingerprint == second.fingerprint
    assert first.to_json() == second.to_json()
    assert [item["path"] for item in first.files] == [
        "pkg/a.py",
        "pkg/b.py",
        "tests/test_a.py",
    ]


def test_python_symbols_are_qualified_and_imports_resolve(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text(
        "from pkg.b import B\n\nclass A:\n    def run(self):\n        return B()\n",
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "b.py").write_text("class B:\n    pass\n", encoding="utf-8")

    index = build_repository_index(tmp_path, include_git_history=False)
    symbols = {(item.path, item.qualified_name, item.kind) for item in index.symbols}
    assert ("pkg/a.py", "A", "class") in symbols
    assert ("pkg/a.py", "A.run", "function") in symbols
    assert ("pkg/b.py", "B", "class") in symbols

    imports = [item for item in index.imports if item.path == "pkg/a.py"]
    assert len(imports) == 1
    assert imports[0].module == "pkg.b"
    assert imports[0].imported_name == "B"
    assert imports[0].resolved_path == "pkg/b.py"


def test_test_classification_and_file_metadata(tmp_path):
    (tmp_path / "tests").mkdir()
    path = tmp_path / "tests" / "test_sample.py"
    path.write_text("def test_value():\n    assert 1 == 1\n", encoding="utf-8")

    index = build_repository_index(tmp_path, include_git_history=False)
    record = index.files[0]
    assert record["path"] == "tests/test_sample.py"
    assert record["is_test"] is True
    assert record["language"] == "python"
    assert record["parse_status"] == "ok"
    assert record["size_bytes"] == path.stat().st_size
    assert len(record["sha256"]) == 64


def test_malformed_python_remains_visible_without_fabricated_structure(tmp_path):
    path = tmp_path / "broken.py"
    path.write_text("def broken(:\n", encoding="utf-8")

    index = build_repository_index(tmp_path, include_git_history=False)
    assert index.files[0]["parse_status"] == "error"
    assert index.symbols == ()
    assert index.imports == ()


def test_json_serialization_is_stable(tmp_path):
    (tmp_path / "README.md").write_text("Atlas\n", encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    decoded = json.loads(index.to_json())
    assert decoded["fingerprint"] == index.fingerprint
    assert decoded["files"][0]["kind"] == "documentation"

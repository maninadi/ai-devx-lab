
from agent.evidence import (
    search_repository,
    read_file_range,
)


def test_search_returns_matching_line_numbers(tmp_path):
    (tmp_path / "pricing.py").write_text(
        "STANDARD = 0.10\n"
        "GOLD = 0.15\n"
        "PROMOTIONAL_GOLD = 0.17\n",
        encoding="utf-8",
    )

    result = search_repository(tmp_path, "GOLD")

    assert result["ok"]
    assert [m["line"] for m in result["matches"]] == [2, 3]
    assert all(m["path"] == "pricing.py" for m in result["matches"])


def test_range_returns_numbered_evidence(tmp_path):
    (tmp_path / "pricing.py").write_text(
        "one\ntwo\nthree\nfour\n",
        encoding="utf-8",
    )

    result = read_file_range(
        tmp_path, "pricing.py", 2, 3
    )

    assert result["ok"]
    assert result["content"] == "2: two\n3: three"
    assert result["total_lines"] == 4


def test_path_traversal_is_rejected(tmp_path):
    result = read_file_range(
        tmp_path, "../secrets.md", 1, 5
    )
    assert not result["ok"]


def test_excessive_line_range_is_rejected(tmp_path):
    (tmp_path / "pricing.py").write_text("hello\n")

    result = read_file_range(
        tmp_path, "pricing.py", 1, 100
    )
    assert not result["ok"]


def test_hidden_files_are_not_searched(tmp_path):
    (tmp_path / ".env").write_text("SECRET=gold")
    (tmp_path / "visible.md").write_text("Gold rules")

    result = search_repository(tmp_path, "gold")

    assert len(result["matches"]) == 1
    assert result["matches"][0]["path"] == "visible.md"


def test_symlink_is_rejected(tmp_path):
    target = tmp_path / "real.md"
    target.write_text("private data")

    (tmp_path / "linked.md").symlink_to(target)

    result = read_file_range(
        tmp_path, "linked.md", 1, 1
    )

    assert not result["ok"]

from pathlib import Path

from agent.tools import execute_tool


def test_read_allowed_file(tmp_path):
    path = tmp_path / "pricing.md"
    path.write_text("Gold discount: 15%")

    result = execute_tool(
        "read_file",
        {"path": "pricing.md"},
        tmp_path,
    )

    assert result["ok"]
    assert "15%" in result["content"]


def test_reject_path_traversal(tmp_path):
    result = execute_tool(
        "read_file",
        {"path": "../secrets.txt"},
        tmp_path,
    )

    assert not result["ok"]


def test_reject_unknown_tool(tmp_path):
    result = execute_tool(
        "delete_repository",
        {},
        tmp_path,
    )

    assert not result["ok"]


def test_reject_hidden_file(tmp_path):
    (tmp_path / ".env").write_text("API_KEY=secret")

    result = execute_tool(
        "read_file",
        {"path": ".env"},
        tmp_path,
    )

    assert not result["ok"]


def test_search_repository_returns_matches():

    result = execute_tool(
        name="search_repository",
        arguments={"query": "Gold"},
        repo_root=Path.cwd(),
    )

    print(result)

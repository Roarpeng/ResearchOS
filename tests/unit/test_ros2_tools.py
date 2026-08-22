"""Unit tests — read-only mcp-ros2 workspace introspection slice.

Builds a synthetic ROS2 workspace under tmp_path and exercises the read-only
tools plus the disabled-by-default codegen / apply_patch placeholders.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.ros2 import server as ros2_server


@pytest.fixture()
def ros2_workspace(tmp_path: Path) -> Path:
    pkg = tmp_path / "src" / "demo_pkg"
    (pkg / "msg").mkdir(parents=True)
    (pkg / "srv").mkdir(parents=True)
    (pkg / "include" / "demo_pkg").mkdir(parents=True)
    (pkg / "launch").mkdir(parents=True)

    (pkg / "package.xml").write_text(
        """<?xml version="1.0"?>
<package format="3">
  <name>demo_pkg</name>
  <version>0.1.0</version>
  <description>Demo ROS2 package for tests.</description>
</package>
""",
        encoding="utf-8",
    )
    (pkg / "msg" / "MyMsg.msg").write_text(
        "# A demo message\nint32 id\nstring name\nfloat64[] values # sampled values\n",
        encoding="utf-8",
    )
    (pkg / "srv" / "MySrv.srv").write_text(
        "string query\n---\nbool ok\nstring reply\n",
        encoding="utf-8",
    )
    (pkg / "include" / "demo_pkg" / "demo.hpp").write_text(
        "#pragma once\n",
        encoding="utf-8",
    )
    (pkg / "launch" / "demo.launch.py").write_text(
        "def generate_launch_description():\n    pass\n",
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# ros2.workspace.list_packages
# ---------------------------------------------------------------------------

def test_list_packages_discovers_package(ros2_workspace: Path) -> None:
    res = ros2_server.ros2_workspace_list_packages(str(ros2_workspace))
    assert res["ok"] is True and res["readonly"] is True
    assert res["count"] == 1
    pkg = res["packages"][0]
    assert pkg["name"] == "demo_pkg"
    assert pkg["version"] == "0.1.0"
    assert "Demo" in pkg["description"]
    assert pkg["path"].endswith("demo_pkg")


def test_list_packages_missing_workspace(tmp_path: Path) -> None:
    res = ros2_server.ros2_workspace_list_packages(str(tmp_path / "nope"))
    assert res["ok"] is False
    assert res["error"] == "workspace_not_found"


# ---------------------------------------------------------------------------
# ros2.pkg.inspect
# ---------------------------------------------------------------------------

def test_inspect_package_lists_dirs_and_launch(ros2_workspace: Path) -> None:
    res = ros2_server.ros2_pkg_inspect(str(ros2_workspace), "demo_pkg")
    assert res["ok"] is True and res["readonly"] is True
    assert res["name"] == "demo_pkg"
    assert res["msg"] == ["msg/MyMsg.msg"]
    assert res["srv"] == ["srv/MySrv.srv"]
    assert res["include"] == ["include/demo_pkg/demo.hpp"]
    assert res["launch"] == ["launch/demo.launch.py"]


def test_inspect_package_missing(ros2_workspace: Path) -> None:
    res = ros2_server.ros2_pkg_inspect(str(ros2_workspace), "missing_pkg")
    assert res["ok"] is False
    assert res["error"] == "package_not_found"


# ---------------------------------------------------------------------------
# ros2.interface.show
# ---------------------------------------------------------------------------

def test_show_interface_msg_fields_with_comments(ros2_workspace: Path) -> None:
    res = ros2_server.ros2_interface_show(str(ros2_workspace), "demo_pkg", "MyMsg")
    assert res["ok"] is True and res["readonly"] is True
    assert res["kind"] == "msg" and res["name"] == "MyMsg"
    assert res["file"] == "msg/MyMsg.msg"

    by_name = {f["name"]: f for f in res["fields"]}
    assert set(by_name) == {"id", "name", "values"}
    assert by_name["id"]["type"] == "int32"
    assert by_name["values"]["type"] == "float64[]"
    assert by_name["values"]["comment"] == "sampled values"


def test_show_interface_srv_sections(ros2_workspace: Path) -> None:
    res = ros2_server.ros2_interface_show(str(ros2_workspace), "demo_pkg", "MySrv")
    assert res["ok"] is True and res["kind"] == "srv"
    assert [f["name"] for f in res["sections"]["request"]] == ["query"]
    assert [f["name"] for f in res["sections"]["response"]] == ["ok", "reply"]


def test_show_interface_missing(ros2_workspace: Path) -> None:
    res = ros2_server.ros2_interface_show(str(ros2_workspace), "demo_pkg", "Nope")
    assert res["ok"] is False
    assert res["error"] == "interface_not_found"


# ---------------------------------------------------------------------------
# ros2.docs.search — placeholder delegating to knowledge.pipeline
# ---------------------------------------------------------------------------

def test_docs_search_placeholder_never_raises(ros2_workspace: Path) -> None:
    res = ros2_server.ros2_docs_search("nav2 navigation")
    assert res["ok"] is True and res["readonly"] is True
    assert isinstance(res["hits"], list)
    assert res["count"] == len(res["hits"])


# ---------------------------------------------------------------------------
# ros2.codegen.suggest / ros2.apply_patch — disabled-by-default placeholders
# ---------------------------------------------------------------------------

def test_codegen_suggest_disabled(ros2_workspace: Path) -> None:
    res = ros2_server.ros2_codegen_suggest(package_name="demo_pkg")
    assert res["ok"] is False
    assert res["status"] == "not_enabled"
    assert "no files are written" in res["message"]


def test_apply_patch_disabled_and_writes_nothing(ros2_workspace: Path) -> None:
    before = sorted(str(p) for p in ros2_workspace.rglob("*"))
    res = ros2_server.ros2_apply_patch(path=str(ros2_workspace / "src" / "demo_pkg"))
    assert res["ok"] is False
    assert res["status"] == "not_enabled"
    after = sorted(str(p) for p in ros2_workspace.rglob("*"))
    assert before == after

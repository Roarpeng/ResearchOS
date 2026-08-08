"""Intent routing: research vs PLC from query text."""

from __future__ import annotations

from gateway.app.services.intent_route import detect_route, extract_plc_path


def test_extract_windows_and_unix_paths() -> None:
    assert extract_plc_path(r"请分析 D:\Export\Line1\Main.xml")
    assert extract_plc_path("看下 /plc_projects/demo.zip 里的逻辑")
    assert extract_plc_path("foo", explicit="/tmp/a.xml") == "/tmp/a.xml"


def test_plc_keyword_without_path_asks_source() -> None:
    d = detect_route("这个 OB1 功能块调用了哪些 FC？")
    assert d.route == "plc_need_source"


def test_plc_path_routes_to_plc() -> None:
    d = detect_route("解析这个工程 /plc_projects/line1/export")
    assert d.route == "plc"
    assert d.path


def test_upload_forces_plc() -> None:
    d = detect_route("随便看看", has_upload=True)
    assert d.route == "plc"


def test_normal_research() -> None:
    d = detect_route("对比协作机器人力控与安全认证差异")
    assert d.route == "research"

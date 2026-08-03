"""ROS2 documentation connector — read-only stub with fake catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class DocEntry:
    id: str
    title: str
    package: str
    url: str
    summary: str
    tags: tuple[str, ...] = ()


class Ros2DocsConnector(Protocol):
    """Read-only interface for ROS2 package / interface docs."""

    def list_packages(self) -> list[str]: ...

    def search(self, query: str, *, limit: int = 10) -> list[DocEntry]: ...

    def get(self, doc_id: str) -> DocEntry | None: ...


FAKE_CATALOG: list[DocEntry] = [
    DocEntry(
        id="ros2_nav2",
        title="Nav2 Navigation Stack",
        package="nav2_bringup",
        url="https://docs.ros.org/en/humble/Tutorials/Navigation.html",
        summary="Lifecycle-managed navigation stack for differential and omnidirectional robots.",
        tags=("navigation", "humble"),
    ),
    DocEntry(
        id="ros2_moveit",
        title="MoveIt 2 Motion Planning",
        package="moveit2",
        url="https://moveit.picknik.ai/",
        summary="Motion planning, kinematics, and manipulation framework for ROS 2.",
        tags=("manipulation", "planning"),
    ),
    DocEntry(
        id="ros2_control",
        title="ros2_control Framework",
        package="ros2_control",
        url="https://control.ros.org/",
        summary="Hardware interfaces, controllers, and real-time robot control abstractions.",
        tags=("control", "hardware"),
    ),
]


class FakeRos2DocsConnector:
    """In-memory fake catalog implementing Ros2DocsConnector."""

    def list_packages(self) -> list[str]:
        return sorted({e.package for e in FAKE_CATALOG})

    def search(self, query: str, *, limit: int = 10) -> list[DocEntry]:
        q = query.lower()
        hits = [
            e
            for e in FAKE_CATALOG
            if q in e.title.lower()
            or q in e.summary.lower()
            or q in e.package.lower()
            or any(q in t for t in e.tags)
        ]
        return hits[:limit]

    def get(self, doc_id: str) -> DocEntry | None:
        for e in FAKE_CATALOG:
            if e.id == doc_id:
                return e
        return None

    def as_dict(self, entry: DocEntry) -> dict[str, Any]:
        return {
            "id": entry.id,
            "title": entry.title,
            "package": entry.package,
            "url": entry.url,
            "summary": entry.summary,
            "tags": list(entry.tags),
            "readonly": True,
        }

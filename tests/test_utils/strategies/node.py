from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThreadNode:
    main: bool
    tasks: list[TaskNode]


@dataclass
class TaskNode:
    thread: ThreadNode

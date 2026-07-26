"""Load and validate benchmark tasks from disk.

A task lives in   benchmark/tasks/<tier>/<TASKID>/
  meta.json       -> parsed into schema.Task
  reference.st    -> the reference Structured Text solution (text)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .schema import Task

# repo root = parent of the plcbench package dir
ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / "benchmark" / "tasks"


@dataclass
class LoadedTask:
    task: Task
    dir: Path
    reference_st: str

    @property
    def id(self) -> str:
        return self.task.id


def load_task(task_dir: Path) -> LoadedTask:
    task_dir = Path(task_dir)
    meta_path = task_dir / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"missing meta.json in {task_dir}")
    task = Task.model_validate(json.loads(meta_path.read_text(encoding="utf-8")))
    ref_path = task_dir / task.reference_st_file
    if not ref_path.exists():
        raise FileNotFoundError(f"missing reference ST file {ref_path}")
    return LoadedTask(task=task, dir=task_dir, reference_st=ref_path.read_text(encoding="utf-8"))


def iter_task_dirs(tasks_dir: Path = TASKS_DIR):
    """Yield every directory that contains a meta.json, sorted by id."""
    tasks_dir = Path(tasks_dir)
    if not tasks_dir.exists():
        return
    for meta in sorted(tasks_dir.rglob("meta.json")):
        yield meta.parent


def load_all(tasks_dir: Path = TASKS_DIR) -> list[LoadedTask]:
    return [load_task(d) for d in iter_task_dirs(tasks_dir)]

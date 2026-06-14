import pytest

from core.commander.models import Edge, TaskDef, WorkflowDef
from core.commander.scheduler import DAGScheduler


def test_serial_execution_order():
    tasks = [
        TaskDef(task_id="a", skill_name="s1"),
        TaskDef(task_id="b", skill_name="s2", depends_on=["a"]),
        TaskDef(task_id="c", skill_name="s3", depends_on=["b"]),
    ]
    edges = [Edge(source="a", target="b"), Edge(source="b", target="c")]
    scheduler = DAGScheduler(tasks, edges)

    order = scheduler.get_execution_order()
    assert order == [["a"], ["b"], ["c"]]


def test_parallel_execution_order():
    tasks = [
        TaskDef(task_id="a", skill_name="s1"),
        TaskDef(task_id="b", skill_name="s2"),
        TaskDef(task_id="c", skill_name="s3", depends_on=["a", "b"]),
    ]
    edges = [Edge(source="a", target="c"), Edge(source="b", target="c")]
    scheduler = DAGScheduler(tasks, edges)

    order = scheduler.get_execution_order()
    assert order[0] == ["a", "b"] or order[0] == ["b", "a"]
    assert order[1] == ["c"]


def test_ready_tasks():
    tasks = [
        TaskDef(task_id="a", skill_name="s1"),
        TaskDef(task_id="b", skill_name="s2", depends_on=["a"]),
    ]
    edges = [Edge(source="a", target="b")]
    scheduler = DAGScheduler(tasks, edges)

    ready = scheduler.get_ready_tasks(set(), set())
    assert len(ready) == 1
    assert ready[0].task_id == "a"

    ready_after_a = scheduler.get_ready_tasks({"a"}, set())
    assert len(ready_after_a) == 1
    assert ready_after_a[0].task_id == "b"


def test_is_complete():
    tasks = [TaskDef(task_id="a", skill_name="s1"), TaskDef(task_id="b", skill_name="s2")]
    scheduler = DAGScheduler(tasks, [])
    assert scheduler.is_complete({"a", "b"}, set()) is True
    assert scheduler.is_complete({"a"}, set()) is False


def test_downstream():
    tasks = [
        TaskDef(task_id="a", skill_name="s1"),
        TaskDef(task_id="b", skill_name="s2", depends_on=["a"]),
        TaskDef(task_id="c", skill_name="s3", depends_on=["b"]),
    ]
    edges = [Edge(source="a", target="b"), Edge(source="b", target="c")]
    scheduler = DAGScheduler(tasks, edges)

    downstream = scheduler.get_downstream("a")
    assert "b" in downstream
    assert "c" in downstream

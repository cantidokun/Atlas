import json

import pytest

from planning.task_checkpoint_store import TaskCheckpointStore
from planning.task_sequence import TaskSequenceDefinition, TaskSequenceSession
from tests.test_task_sequence import _task


def test_checkpoint_store_round_trips_integrity_bound_checkpoint(tmp_path):
    definition = TaskSequenceDefinition((_task("first", "set_first", "first", 1),))
    reducer = lambda evidence: evidence[0]
    execute = lambda tool, args: {"key": args["key"], "value": args.get("value", 0)}
    sequence = TaskSequenceSession(definition, execute, (reducer,))
    checkpoint = sequence.checkpoint()

    store = TaskCheckpointStore(tmp_path / "sequence.json")
    store.save(checkpoint)
    assert store.load() == checkpoint
    resumed = store.load_session(definition, execute, (reducer,))
    assert resumed.index == 0


def test_checkpoint_store_rejects_tampered_disk_payload(tmp_path):
    definition = TaskSequenceDefinition((_task("first", "set_first", "first", 1),))
    reducer = lambda evidence: evidence[0]
    execute = lambda tool, args: {"key": args["key"], "value": args.get("value", 0)}
    checkpoint = TaskSequenceSession(definition, execute, (reducer,)).checkpoint()
    path = tmp_path / "sequence.json"
    path.write_text(json.dumps(checkpoint), encoding="utf-8")

    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["current_task"] = "forged"
    path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(ValueError, match="integrity digest"):
        TaskCheckpointStore(path).load_session(definition, execute, (reducer,))


def test_checkpoint_store_rejects_non_object_checkpoint(tmp_path):
    path = tmp_path / "sequence.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="stored checkpoint"):
        TaskCheckpointStore(path).load()

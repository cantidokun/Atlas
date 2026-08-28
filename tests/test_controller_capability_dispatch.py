"""Tests for provider-neutral controller capability dispatch."""

import pytest

from controller.capability_dispatch import ControllerCapabilityDispatcher


def test_dispatcher_resolves_single_matching_capability_without_executing_it():
    dispatcher = ControllerCapabilityDispatcher()
    handler = object()
    called = []

    def predicate(task_text, context):
        called.append((task_text, dict(context)))
        return context.get("provider") == "unreal"

    dispatcher.register("unreal", predicate, handler)
    result = dispatcher.resolve("make production", {"provider": "unreal"})

    assert result is not None
    assert result.handler is handler
    assert called == [("make production", {"provider": "unreal"})]


def test_dispatcher_returns_none_when_nothing_matches():
    dispatcher = ControllerCapabilityDispatcher()
    dispatcher.register("unreal", lambda _task, _context: False, object())

    assert dispatcher.resolve("ordinary task", {}) is None


def test_dispatcher_rejects_ambiguous_matches_fail_closed():
    dispatcher = ControllerCapabilityDispatcher()
    dispatcher.register("first", lambda _task, _context: True, object())
    dispatcher.register("second", lambda _task, _context: True, object())

    with pytest.raises(RuntimeError, match="multiple controller capabilities matched"):
        dispatcher.resolve("ambiguous", {})


def test_dispatcher_rejects_duplicate_registration():
    dispatcher = ControllerCapabilityDispatcher()
    dispatcher.register("unreal", lambda _task, _context: True, object())

    with pytest.raises(ValueError, match="already registered"):
        dispatcher.register("unreal", lambda _task, _context: True, object())

"""Tests for provider-neutral controller capability dispatch."""

import pytest

from controller.capability_dispatch import ControllerCapabilityDispatcher
from controller.capability_request import CapabilityRequest


def test_dispatcher_resolves_single_matching_capability_without_executing_it():
    dispatcher = ControllerCapabilityDispatcher()
    handler = object()
    called = []

    def predicate(request):
        called.append(request)
        return request.normalized_provider == "unreal"

    dispatcher.register("unreal", predicate, handler)
    request = CapabilityRequest("production", "Unreal", {"production": True})
    result = dispatcher.resolve(request)

    assert result is not None
    assert result.handler is handler
    assert called == [request]


def test_dispatcher_returns_none_when_nothing_matches():
    dispatcher = ControllerCapabilityDispatcher()
    dispatcher.register("unreal", lambda _request: False, object())

    assert dispatcher.resolve(CapabilityRequest("ordinary", None, {})) is None


def test_dispatcher_rejects_ambiguous_matches_fail_closed():
    dispatcher = ControllerCapabilityDispatcher()
    dispatcher.register("first", lambda _request: True, object())
    dispatcher.register("second", lambda _request: True, object())

    with pytest.raises(RuntimeError, match="multiple controller capabilities matched"):
        dispatcher.resolve(CapabilityRequest("ambiguous", None, {}))


def test_dispatcher_rejects_duplicate_registration():
    dispatcher = ControllerCapabilityDispatcher()
    dispatcher.register("unreal", lambda _request: True, object())

    with pytest.raises(ValueError, match="already registered"):
        dispatcher.register("unreal", lambda _request: True, object())

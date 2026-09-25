"""Tests the LangGraph orchestration specifically -- separate from
tests/test_engine.py's tests, which cover the plain agent.SchemePilot
version. If langgraph isn't installed, these tests are skipped rather
than failing the whole suite.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest

langgraph = pytest.importorskip("langgraph", reason="langgraph not installed")
from graph_agent import SchemePilotGraph


def test_graph_runs_a_turn_and_asks_a_question():
    a = SchemePilotGraph(thread_id="test-1")
    out = a.handle("I'm 23, live in Karnataka, family income is 4.5 lakh, I'm a student, we don't own a house")
    assert out["next_question"] is not None
    assert "age" in a.profile and a.profile["age"] == 23
    assert out["next_question"]["field"] not in a.profile


def test_graph_state_persists_across_turns():
    a = SchemePilotGraph(thread_id="test-2")
    out1 = a.handle("I'm 23, Karnataka, family income 4.5 lakh, student, no house")
    field = out1["next_question"]["field"]
    out2 = a.handle("urban" if field == "residence" else "no")
    assert field in a.asked
    # profile from turn 1 should still be there after turn 2
    assert a.profile.get("age") == 23


def test_two_threads_dont_share_state():
    a = SchemePilotGraph(thread_id="thread-a")
    b = SchemePilotGraph(thread_id="thread-b")
    a.handle("I'm 40, Maharashtra, farmer, income 2 lakh")
    assert "age" not in b.profile
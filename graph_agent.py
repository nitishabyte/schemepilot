"""LangGraph-based agent orchestration.

This is the one file that pulls in an agent framework. It wires the same
building blocks agent.py uses -- profile extraction, the deterministic
eligibility engine, and adaptive question-picking -- into an explicit
LangGraph StateGraph, so the *control flow* is what the framework governs.

Deliberately unchanged by this: engine.py still has zero LLM calls in it.
The framework orchestrates *when* to extract, evaluate, and ask -- it still
never decides eligibility itself. That's the same hybrid design as agent.py,
just expressed as a graph instead of a hand-written loop.

Per-turn flow:   extract -> evaluate -> ask -> END
Multi-turn state persists across calls via LangGraph's checkpointer, keyed
by a thread_id -- the standard LangGraph pattern for a conversational agent,
rather than re-building state from scratch on every message.
"""
from typing import Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from audit import log_evaluation
from engine import evaluate_all, explain, load_schemes, what_if
from llm import extract_profile
from questions import next_question
from user_profile import SKIP, parse_answer

SCHEMES = load_schemes()


class AgentState(TypedDict):
    text: str
    profile: dict
    asked: list
    pending: Optional[str]
    results: list
    next_question: Optional[dict]
    turn_updates: dict


def node_extract(state: AgentState) -> AgentState:
    """Merge the user's latest message into the profile.

    If a question was pending from the previous turn, its answer is parsed
    directly against that field first; free-text extraction still runs on
    top so a person can volunteer extra facts unprompted.
    """
    updates = {}
    pending = state.get("pending")
    text = state["text"]
    asked = list(state.get("asked", []))

    if pending:
        if not SKIP.search(text):
            v = parse_answer(pending, text)
            if v is not None:
                updates[pending] = v
        if pending not in asked:
            asked.append(pending)

    for k, v in extract_profile(text).items():
        updates.setdefault(k, v)

    return {
        **state,
        "profile": {**state["profile"], **updates},
        "asked": asked,
        "turn_updates": updates,
    }


def node_evaluate(state: AgentState) -> AgentState:
    """Run the deterministic engine. No LLM involvement in this node."""
    results = evaluate_all(SCHEMES, state["profile"])
    log_evaluation(state["profile"], results)
    return {**state, "results": results}


def node_ask(state: AgentState) -> AgentState:
    """Pick whichever unresolved field affects the most still-undecided schemes."""
    q = next_question(state["results"], set(state["asked"]))
    return {**state, "next_question": q, "pending": q["field"] if q else None}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("extract", node_extract)
    g.add_node("evaluate", node_evaluate)
    g.add_node("ask", node_ask)
    g.set_entry_point("extract")
    g.add_edge("extract", "evaluate")
    g.add_edge("evaluate", "ask")
    g.add_edge("ask", END)
    return g.compile(checkpointer=MemorySaver())


class SchemePilotGraph:
    """Drop-in replacement for agent.SchemePilot, backed by a compiled LangGraph graph.

    Same public interface (.profile, .asked, .handle(), .why_not(), .simulate())
    so app.py and the eval scripts don't need to know which one is underneath.
    """

    def __init__(self, thread_id: str = "default"):
        self.graph = build_graph()
        self.config = {"configurable": {"thread_id": thread_id}}
        self._state: AgentState = {
            "text": "", "profile": {}, "asked": [], "pending": None,
            "results": [], "next_question": None, "turn_updates": {},
        }

    @property
    def profile(self) -> dict:
        return self._state["profile"]

    @property
    def asked(self) -> set:
        return set(self._state["asked"])

    def handle(self, text: str) -> dict:
        self._state = {**self._state, "text": text}
        self._state = self.graph.invoke(self._state, config=self.config)
        return {
            "updates": self._state["turn_updates"],
            "results": self._state["results"],
            "next_question": self._state["next_question"],
        }

    def why_not(self, scheme_id: str) -> str:
        r = next(r for r in evaluate_all(SCHEMES, self.profile) if r.scheme_id == scheme_id)
        return explain(r)

    def simulate(self, changes: dict) -> list:
        return what_if(SCHEMES, self.profile, changes)
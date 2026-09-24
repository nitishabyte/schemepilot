import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from engine import *
from user_profile import parse_number, rule_based_extract
from agent import SchemePilot

S = {"id": "t", "name": "T", "documents": ["a", "b"], "criteria": [
    {"field": "age", "op": ">=", "value": 18},
    {"field": "household_income", "op": "<=", "value": 500000},
    {"field": "state", "op": "==", "value": "Karnataka"}]}


def test_likely():
    assert evaluate_scheme(S, {"age": 23, "household_income": 450000, "state": "Karnataka"}).verdict == LIKELY


def test_fail_beats_unknown():
    assert evaluate_scheme(S, {"age": 15}).verdict == INELIGIBLE


def test_unknown_is_potential():
    r = evaluate_scheme(S, {"age": 23})
    assert r.verdict == POTENTIAL and r.missing_fields == ["household_income", "state"]


def test_boundary_inclusive():
    assert eval_criterion(S["criteria"][1], {"household_income": 500000}).status == PASS


def test_what_if():
    p = {"age": 23, "household_income": 600000, "state": "Karnataka"}
    d = what_if([S], p, {"household_income": 300000})
    assert d == [{"scheme_id": "t", "name": "T", "before": INELIGIBLE, "after": LIKELY}]


def test_numbers():
    assert parse_number("4.5 lakh") == 450000 and parse_number("₹3,00,000") == 300000 and parse_number("40k") == 40000


def test_extraction_example():
    p = rule_based_extract("I'm 23, live in Karnataka, family income is ₹4.5 lakh, I'm a student, we don't own a house")
    assert p == {"age": 23, "household_income": 450000, "state": "Karnataka", "is_student": True, "owns_house": False}


def test_agent_asks_then_updates():
    a = SchemePilot(audit=False)
    out = a.handle("I'm 23, Karnataka, family income 4.5 lakh, I'm a student, we don't own a house")
    assert out["next_question"] is not None
    assert out["next_question"]["field"] not in a.profile
    field = out["next_question"]["field"]
    a.handle("urban" if field == "residence" else "no")
    assert field in a.asked

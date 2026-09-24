"""Deterministic eligibility engine. NO LLM in here, by design.

Each criterion evaluates to PASS / FAIL / UNKNOWN.
Scheme verdict:
  any FAIL     -> INELIGIBLE
  else any UNKNOWN -> POTENTIAL
  else         -> LIKELY
"""
from dataclasses import dataclass, field, asdict
import json
from pathlib import Path

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"
LIKELY, POTENTIAL, INELIGIBLE = "LIKELY", "POTENTIAL", "INELIGIBLE"

OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


@dataclass
class CriterionResult:
    field: str
    op: str
    expected: object
    actual: object
    status: str


@dataclass
class SchemeResult:
    scheme_id: str
    name: str
    verdict: str
    criteria: list = field(default_factory=list)
    missing_fields: list = field(default_factory=list)
    documents: list = field(default_factory=list)
    source_url: str = ""
    verified: bool = False

    def to_dict(self):
        return asdict(self)


def load_schemes(path=None):
    path = Path(path or Path(__file__).parent / "data" / "schemes.json")
    return json.loads(path.read_text(encoding="utf-8"))


def eval_criterion(c, profile):
    actual = profile.get(c["field"])
    if actual is None:
        return CriterionResult(c["field"], c["op"], c["value"], None, UNKNOWN)
    try:
        ok = OPS[c["op"]](actual, c["value"])
    except TypeError:  # e.g. comparing str to int -> treat as unknown, not a crash
        return CriterionResult(c["field"], c["op"], c["value"], actual, UNKNOWN)
    return CriterionResult(c["field"], c["op"], c["value"], actual, PASS if ok else FAIL)


def evaluate_scheme(scheme, profile):
    results = [eval_criterion(c, profile) for c in scheme["criteria"]]
    statuses = {r.status for r in results}
    verdict = INELIGIBLE if FAIL in statuses else POTENTIAL if UNKNOWN in statuses else LIKELY
    return SchemeResult(
        scheme_id=scheme["id"],
        name=scheme["name"],
        verdict=verdict,
        criteria=results,
        missing_fields=sorted({r.field for r in results if r.status == UNKNOWN}),
        documents=scheme.get("documents", []),
        source_url=scheme.get("source_url", ""),
        verified=scheme.get("verified", False),
    )


def evaluate_all(schemes, profile):
    order = {LIKELY: 0, POTENTIAL: 1, INELIGIBLE: 2}
    res = [evaluate_scheme(s, profile) for s in schemes]
    return sorted(res, key=lambda r: (order[r.verdict], r.name))


def what_if(schemes, profile, changes):
    """Re-run the engine with modified fields; return verdict changes."""
    before = {r.scheme_id: r for r in evaluate_all(schemes, profile)}
    after = {r.scheme_id: r for r in evaluate_all(schemes, {**profile, **changes})}
    diff = []
    for sid, b in before.items():
        a = after[sid]
        if a.verdict != b.verdict:
            diff.append({"scheme_id": sid, "name": a.name, "before": b.verdict, "after": a.verdict})
    return diff


_OP_TEXT = {"==": "must be", "!=": "must not be", ">=": "must be at least", "<=": "must be at most",
            ">": "must be more than", "<": "must be less than", "in": "must be one of", "not_in": "must not be one of"}


def explain(result):
    """Deterministic, per-criterion explanation (great for 'why am I not eligible?')."""
    lines = [f"{result.name}: {result.verdict}"]
    for c in result.criteria:
        mark = {PASS: "✓", FAIL: "✗", UNKNOWN: "?"}[c.status]
        actual = "not provided" if c.actual is None else c.actual
        lines.append(f"  {mark} {c.field} {_OP_TEXT[c.op]} {c.expected} (yours: {actual})")
    return "\n".join(lines)


def document_checklist(result, held):
    held = set(held or [])
    return {"have": [d for d in result.documents if d in held],
            "need": [d for d in result.documents if d not in held]}

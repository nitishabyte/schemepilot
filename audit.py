import json, time
from pathlib import Path

LOG = Path(__file__).parent / "logs" / "audit.jsonl"


def log_evaluation(profile, results):
    LOG.parent.mkdir(exist_ok=True)
    rec = {"ts": time.time(), "profile": profile,
           "results": [{"scheme": r.scheme_id, "verdict": r.verdict,
                        "criteria": [{"f": c.field, "op": c.op, "exp": c.expected, "act": c.actual, "s": c.status}
                                     for c in r.criteria]} for r in results]}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

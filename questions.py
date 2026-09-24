"""Adaptive question selection: ask about the field that is UNKNOWN in the most still-viable schemes."""
from collections import Counter
from engine import INELIGIBLE
from user_profile import FIELDS, FIELD_ORDER


def next_question(results, asked):
    scores = Counter()
    for r in results:
        if r.verdict == INELIGIBLE:
            continue  # no point resolving unknowns for a scheme that already failed
        for f in r.missing_fields:
            if f not in asked:
                scores[f] += 1
    if not scores:
        return None
    field = max(scores, key=lambda f: (scores[f], -FIELD_ORDER.index(f)))
    return {"field": field, "question": FIELDS[field]["q"], "affects": scores[field]}

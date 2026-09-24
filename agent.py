"""SchemePilot agent loop: extract -> update profile -> evaluate -> pick next question."""
from engine import load_schemes, evaluate_all, what_if, explain, INELIGIBLE
from user_profile import FIELDS, SKIP, parse_answer
from llm import extract_profile
from questions import next_question
from audit import log_evaluation


class SchemePilot:
    def __init__(self, schemes=None, audit=True):
        self.schemes = schemes or load_schemes()
        self.profile = {}
        self.asked = set()
        self.pending = None  # field we just asked about
        self.audit = audit

    def handle(self, text):
        updates = {}
        if self.pending:
            if SKIP.search(text):
                pass  # user doesn't know; don't ask again
            else:
                v = parse_answer(self.pending, text)
                if v is not None:
                    updates[self.pending] = v
            self.asked.add(self.pending)
        # free-text extraction still runs so users can volunteer extra facts
        for k, v in extract_profile(text).items():
            updates.setdefault(k, v)
        self.profile.update(updates)

        results = evaluate_all(self.schemes, self.profile)
        if self.audit:
            log_evaluation(self.profile, results)
        q = next_question(results, self.asked)
        self.pending = q["field"] if q else None
        return {"updates": updates, "results": results, "next_question": q}

    def why_not(self, scheme_id):
        r = next(r for r in evaluate_all(self.schemes, self.profile) if r.scheme_id == scheme_id)
        return explain(r)

    def simulate(self, changes):
        return what_if(self.schemes, self.profile, changes)

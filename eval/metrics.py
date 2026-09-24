"""Shared scoring helpers. Kept dependency-free so eval scripts stay easy to read."""


def field_prf(extracted: dict, stated: dict):
    """Precision/recall/F1 of an extractor against the fields a text actually stated.
    Any key in `extracted` that isn't in `stated` counts as unsupported-by-text
    (whether or not it happens to be correct), which is the fair way to grade
    extraction from a single message: the model has no basis for guessing it yet.
    """
    correct = sum(1 for k, v in stated.items() if extracted.get(k) == v)
    wrong_value = sum(1 for k, v in stated.items() if k in extracted and extracted[k] != v)
    missed = sum(1 for k in stated if k not in extracted)
    unsupported = [k for k in extracted if k not in stated]

    precision = correct / len(extracted) if extracted else 1.0
    recall = correct / len(stated) if stated else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "correct": correct, "wrong_value": wrong_value, "missed": missed,
        "unsupported": unsupported, "precision": precision, "recall": recall, "f1": f1,
    }


def aggregate_prf(per_persona_results):
    n = len(per_persona_results)
    if n == 0:
        return {}
    avg = lambda k: sum(r[k] for r in per_persona_results) / n
    total_unsupported = sum(len(r["unsupported"]) for r in per_persona_results)
    return {
        "n_personas": n,
        "avg_precision": round(avg("precision"), 3),
        "avg_recall": round(avg("recall"), 3),
        "avg_f1": round(avg("f1"), 3),
        "total_wrong_value": sum(r["wrong_value"] for r in per_persona_results),
        "total_missed": sum(r["missed"] for r in per_persona_results),
        "total_unsupported_fields": total_unsupported,
    }


def verdict_accuracy(pred: dict, truth: dict):
    """pred/truth: scheme_id -> verdict string. Returns accuracy + mismatches."""
    ids = list(truth)
    correct = sum(1 for sid in ids if pred.get(sid) == truth[sid])
    mismatches = [{"scheme": sid, "true": truth[sid], "pred": pred.get(sid)}
                  for sid in ids if pred.get(sid) != truth[sid]]
    false_likely = [m for m in mismatches if m["pred"] == "LIKELY" and m["true"] != "LIKELY"]
    return {
        "n": len(ids), "correct": correct,
        "accuracy": round(correct / len(ids), 3) if ids else 1.0,
        "mismatches": mismatches,
        "false_likely_count": len(false_likely),
    }


def markdown_table(rows, headers):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)

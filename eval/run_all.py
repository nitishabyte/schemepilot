"""Runs every eval script and writes eval/report.md summarizing the numbers.
Usage:  python eval/run_all.py
(Run from the project root, or anywhere -- paths are resolved relative to this file.)
"""
import json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent


def run(script):
    print(f"\n{'='*60}\nRunning {script}\n{'='*60}")
    subprocess.run([sys.executable, str(HERE / script)], check=False)


def load(name):
    p = HERE / name
    return json.loads(p.read_text()) if p.exists() else None


if __name__ == "__main__":
    run("run_extraction_eval.py")
    run("run_pipeline_eval.py")
    run("run_llm_baseline.py")

    extraction = load("extraction_results.json")
    pipeline = load("pipeline_results.json")
    llm_baseline = load("llm_baseline_results.json")

    lines = ["# SchemePilot — Evaluation Report\n"]

    lines.append("## 1. Profile extraction accuracy\n")
    if extraction:
        for name, agg in extraction.items():
            lines.append(f"**{name}**: precision {agg['avg_precision']}, recall {agg['avg_recall']}, "
                          f"F1 {agg['avg_f1']}, unsupported fields {agg['total_unsupported_fields']}, "
                          f"wrong values {agg['total_wrong_value']} (n={agg['n_personas']} personas)\n")
    else:
        lines.append("_Not run._\n")

    lines.append("\n## 2. Turn-1 verdict accuracy & adaptive questioning\n")
    if pipeline:
        t1 = pipeline["turn1"]
        mean_acc = sum(r[1] for r in t1) / len(t1)
        qt = pipeline["questioning"]
        mean_a = sum(r[1] for r in qt) / len(qt)
        mean_f = sum(r[2] for r in qt) / len(qt)
        lines.append(f"Mean turn-1 verdict accuracy (message alone, no follow-ups): **{mean_acc:.3f}**\n")
        lines.append(f"Mean follow-up questions — adaptive: **{mean_a:.2f}**, fixed-form: **{mean_f:.2f}** "
                      f"({100*(1 - mean_a/mean_f):.0f}% fewer questions)\n")
    else:
        lines.append("_Not run._\n")

    lines.append("\n## 3. Hybrid engine vs LLM-only baseline\n")
    if llm_baseline:
        lines.append(f"LLM-only accuracy: **{llm_baseline['mean_accuracy']:.3f}**  \n"
                      f"LLM-only run-to-run consistency: **{llm_baseline['consistency_pct']:.1f}%** "
                      f"({llm_baseline['flips']}/{llm_baseline['total_pairs']} verdicts flipped between identical runs)  \n"
                      f"Hybrid rules engine consistency: **100%** (deterministic; see tests/test_engine.py)\n")
    else:
        lines.append("_Not run — set ANTHROPIC_API_KEY and re-run `python eval/run_llm_baseline.py`._\n")

    out = HERE / "report.md"
    out.write_text("\n".join(lines))
    print(f"\n\nReport written -> {out}")

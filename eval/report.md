# SchemePilot — Evaluation Report

## 1. Profile extraction accuracy

**rule_based**: precision 0.934, recall 0.729, F1 0.796, unsupported fields 3, wrong values 1 (n=15 personas)

**llm**: precision 0.978, recall 0.78, F1 0.862, unsupported fields 1, wrong values 0 (n=15 personas)


## 2. Turn-1 verdict accuracy & adaptive questioning

Mean turn-1 verdict accuracy (message alone, no follow-ups): **0.400**

Mean follow-up questions — adaptive: **2.87**, fixed-form: **6.73** (57% fewer questions)


## 3. Hybrid engine vs LLM-only baseline

LLM-only accuracy: **0.853**  
LLM-only run-to-run consistency: **97.3%** (2/75 verdicts flipped between identical runs)  
Hybrid rules engine consistency: **100%** (deterministic; see tests/test_engine.py)

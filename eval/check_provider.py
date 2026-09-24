"""Quick single-call test so you're not burning through 75 calls just to debug an error.
Usage: python eval/check_provider.py
"""
import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from llm import chat

if os.getenv("GROQ_API_KEY"):
    print(f"GROQ_API_KEY is set, starts with: {os.environ['GROQ_API_KEY'][:6]}...")
    # List exactly which models this key can actually use, since Groq's free-tier
    # model access can vary by account and the default name can go stale.
    import json, urllib.error, urllib.request
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
                 "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            models = [m["id"] for m in json.loads(resp.read())["data"]]
        print(f"Models available to your key ({len(models)}):")
        for m in models:
            print(f"  - {m}")
        print(f"\nCurrently configured to use: {os.getenv('SCHEMEPILOT_GROQ_MODEL', 'openai/gpt-oss-20b')}")
        print("If that's not in the list above, set SCHEMEPILOT_GROQ_MODEL to one that is.")
    except urllib.error.HTTPError as e:
        print(f"Could not list models: HTTP {e.code}: {e.read().decode(errors='replace')}")
elif os.getenv("ANTHROPIC_API_KEY"):
    print(f"ANTHROPIC_API_KEY is set, starts with: {os.environ['ANTHROPIC_API_KEY'][:8]}...")
else:
    print("No API key found in the environment (checked GROQ_API_KEY, ANTHROPIC_API_KEY).")
    sys.exit(1)

print("Making one test call...")
result = chat("Reply with exactly one word: OK", "ping", max_tokens=50)
if not result:
    print("\nCall 'succeeded' but returned empty/no text. Let's look at the raw response.")
    import json as _json, urllib.request as _ur
    model = os.getenv("SCHEMEPILOT_GROQ_MODEL", "openai/gpt-oss-20b")
    payload = {"model": model, "max_completion_tokens": 50, "temperature": 0,
               "messages": [{"role": "system", "content": "Reply with exactly one word: OK"}, {"role": "user", "content": "ping"}]}
    if model.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = "low"
    req = _ur.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=_json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}", "Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"},
    )
    with _ur.urlopen(req, timeout=30) as resp:
        print(_json.dumps(_json.loads(resp.read()), indent=2))
else:
    print(f"\nSuccess. Response: {result!r}")
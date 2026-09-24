"""LLM-based profile extraction with a rule-based fallback, plus a generic
chat() function the eval scripts reuse for the LLM-only baseline.

Provider is chosen by whichever key is set (checked in this order):
  GROQ_API_KEY       -- free, no billing required: https://console.groq.com/keys
  ANTHROPIC_API_KEY  -- paid: https://console.anthropic.com
If neither is set, everything falls back to the rule-based extractor in user_profile.py.
"""
import json, os, re, time, urllib.error, urllib.request
from user_profile import FIELDS, coerce, rule_based_extract

ANTHROPIC_MODEL = os.getenv("SCHEMEPILOT_MODEL", "claude-sonnet-5")
GROQ_MODEL = os.getenv("SCHEMEPILOT_GROQ_MODEL", "openai/gpt-oss-20b")

SYSTEM = f"""Extract facts about a person's household from their message for a government-scheme eligibility tool.
Return ONLY a JSON object using these keys (omit any key not clearly stated; never guess):
{json.dumps({k: (v.get('choices') or v['type']) for k, v in FIELDS.items()})}
household_income is annual household income in rupees as an integer (4.5 lakh = 450000).
No markdown, no commentary."""


_last_groq_call = 0.0
_MIN_GROQ_INTERVAL = 2.2  # seconds; keeps us under Groq free tier's 30 requests/minute


def _groq_chat_once(system, user, max_tokens):
    global _last_groq_call
    wait = _MIN_GROQ_INTERVAL - (time.time() - _last_groq_call)
    if wait > 0:
        time.sleep(wait)
    _last_groq_call = time.time()

    payload = {
        "model": GROQ_MODEL, "max_completion_tokens": max_tokens, "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if GROQ_MODEL.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = "low"  # keep reasoning tokens small so the real answer isn't cut off
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Groq's Cloudflare front-end blocks bare/scripted requests (no User-Agent etc.)
            # with Cloudflare error 1010, so we set headers that look like a normal client.
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"Groq HTTP {e.code}: {body}") from e
    return data["choices"][0]["message"]["content"]


def _wait_seconds_from_error(msg, default=2.5):
    """Parse Groq's 'Please try again in Xs' / 'Xms' hint out of the error body."""
    m = re.search(r"try again in ([\d.]+)(m?s)", msg)
    if not m:
        return default
    val = float(m.group(1))
    return (val / 1000 if m.group(2) == "ms" else val) + 0.2  # small buffer


def _groq_chat(system, user, max_tokens, retries=8):
    for attempt in range(retries):
        try:
            return _groq_chat_once(system, user, max_tokens)
        except RuntimeError as e:
            if "rate_limit_exceeded" in str(e):
                wait = _wait_seconds_from_error(str(e))
                print(f"[llm] rate limited, waiting {wait:.1f}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("Gave up after repeated rate limiting")


def _anthropic_chat(system, user, max_tokens):
    import anthropic
    msg = anthropic.Anthropic().messages.create(
        model=ANTHROPIC_MODEL, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}])
    return msg.content[0].text


def chat(system, user, max_tokens=600):
    """Generic single-turn chat call. Returns None if no provider is configured or the call fails."""
    try:
        if os.getenv("GROQ_API_KEY"):
            return _groq_chat(system, user, max_tokens)
        if os.getenv("ANTHROPIC_API_KEY"):
            return _anthropic_chat(system, user, max_tokens)
    except Exception as e:
        print(f"[llm] provider call failed: {e}")
    return None


def llm_extract(text):
    raw = chat(SYSTEM, text, max_tokens=600)
    if raw is None:
        return None
    try:
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
        return json.loads(cleaned)
    except Exception as e:
        print(f"[llm] JSON parse failed, falling back to rules: {e}")
        return None


def extract_profile(text):
    raw = llm_extract(text)
    if raw is None:
        raw = rule_based_extract(text)
    return {k: v for k, v in ((k, coerce(k, v)) for k, v in raw.items()) if v is not None}
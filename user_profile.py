"""Profile schema, value coercion, and rule-based parsing (works with no API key)."""
import re

FIELDS = {
    "age": {"type": "int", "q": "How old are you?"},
    "state": {"type": "str", "q": "Which state do you live in?"},
    "household_income": {"type": "int", "q": "What is your total annual household income (in ₹)?"},
    "is_student": {"type": "bool", "q": "Are you currently a student?"},
    "social_category": {"type": "enum", "choices": ["General", "OBC", "SC", "ST"],
                        "q": "Which social category do you belong to (General / OBC / SC / ST)?"},
    "residence": {"type": "enum", "choices": ["urban", "rural"], "q": "Do you live in an urban or rural area?"},
    "owns_house": {"type": "bool", "q": "Does your family own a residential house?"},
    "gender": {"type": "enum", "choices": ["male", "female", "other"], "q": "What is your gender (male / female / other)?"},
    "is_farmer": {"type": "bool", "q": "Does your family own agricultural land / work as farmers?"},
    "is_income_tax_payer": {"type": "bool", "q": "Does anyone in your household pay income tax?"},
    "is_head_of_family": {"type": "bool", "q": "Are you the head of your household?"},
}
FIELD_ORDER = list(FIELDS)  # tie-break priority when choosing next question

STATES = ["Andhra Pradesh", "Assam", "Bihar", "Delhi", "Goa", "Gujarat", "Haryana", "Karnataka", "Kerala",
          "Madhya Pradesh", "Maharashtra", "Odisha", "Punjab", "Rajasthan", "Tamil Nadu", "Telangana",
          "Uttar Pradesh", "West Bengal"]  # extend as needed

YES = {"yes", "y", "yeah", "yep", "true", "sure", "correct"}
NO = {"no", "n", "nope", "false", "nah"}
SKIP = re.compile(r"\b(don'?t know|not sure|no idea|skip|unsure)\b", re.I)


def parse_number(text):
    """'4.5 lakh' -> 450000, '₹3,00,000' -> 300000, '40k' -> 40000."""
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(lakhs?|lacs?|crores?|k|l)?\b", text.replace("₹", " "), re.I)
    if not m:
        return None
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    mult = {"lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5,
            "crore": 1e7, "crores": 1e7, "k": 1e3}.get((m.group(2) or "").lower(), 1)
    return int(n * mult)


def coerce(field, value):
    """Validate/normalise a value for a field. Returns None if invalid."""
    spec = FIELDS.get(field)
    if spec is None or value is None:
        return None
    t = spec["type"]
    try:
        if t == "int":
            v = int(float(value)) if not isinstance(value, str) else parse_number(value)
            return v if v is not None and v >= 0 else None
        if t == "bool":
            if isinstance(value, bool):
                return value
            s = str(value).strip().lower()
            return True if s in YES else False if s in NO else None
        if t == "enum":
            for c in spec["choices"]:
                if str(value).strip().lower() == c.lower():
                    return c
            return None
        if t == "str":
            s = str(value).strip()
            for st in STATES:
                if s.lower() == st.lower():
                    return st
            return s.title() or None
    except (ValueError, TypeError):
        return None


def parse_answer(field, text):
    """Interpret a short reply to a specific pending question."""
    t = text.strip()
    spec = FIELDS[field]["type"]
    if spec == "bool":
        first = re.split(r"\W+", t.lower())[0] if t else ""
        return coerce(field, first)
    if spec == "int":
        return coerce(field, t)
    if spec == "enum":
        for c in FIELDS[field]["choices"]:
            if re.search(rf"\b{c}\b", t, re.I):
                return c
        return None
    if spec == "str":
        for st in STATES:
            if st.lower() in t.lower():
                return st
        return coerce(field, t)


def rule_based_extract(text):
    """Regex fallback for free-text intake. Deliberately conservative."""
    out, low = {}, text.lower()
    m = re.search(r"\b(\d{1,2})\s*(?:years?\s*old|yrs?|y/?o)\b", low) or re.search(r"\b(?:i am|i'm|age(?: is)?)\s*(\d{1,2})\b", low)
    if m:
        out["age"] = int(m.group(1))
    m = (re.search(r"(?:income|earn\w*)[^\d₹]{0,30}(?:₹|rs\.?|inr)?\s*([\d,.]+\s*(?:lakhs?|lacs?|l|k|crores?)?)", low)
         or re.search(r"(?:₹|rs\.?\s*|inr\s*)([\d,.]+\s*(?:lakhs?|lacs?|l|k|crores?)?)", low))
    if m:
        v = parse_number(m.group(1))
        if v:
            out["household_income"] = v
    for st in STATES:
        if st.lower() in low:
            out["state"] = st
    if re.search(r"\bnot a student\b", low):
        out["is_student"] = False
    elif re.search(r"\bstudent|studying|college\b", low):
        out["is_student"] = True
    if re.search(r"\burban|\bcity\b", low):
        out["residence"] = "urban"
    elif re.search(r"\brural|\bvillage\b", low):
        out["residence"] = "rural"
    if re.search(r"(don'?t|do not|doesn'?t|no)\s+(own|have)\s+(a\s+)?(house|home)", low):
        out["owns_house"] = False
    elif re.search(r"\b(own|have)\s+(a\s+)?(house|home)", low):
        out["owns_house"] = True
    if re.search(r"\bfemale|woman|girl\b", low):
        out["gender"] = "female"
    elif re.search(r"\bmale\b|\bman\b|\bboy\b", low):
        out["gender"] = "male"
    for c in ("SC", "ST", "OBC"):
        if re.search(rf"\b{c}\b", text):
            out["social_category"] = c
    if re.search(r"\bfarmer|farming|agricultur", low):
        out["is_farmer"] = True
    return out

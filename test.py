# app.py (v4 — Built‑in Q&A + Animated UI)
# Functional Chatbot for Personalised Medicines (offline, lab‑friendly)
# What’s new in v4:
# - Preloaded Q&A from your dataset (Diabetes, Cancer, Abdominal Ultrasound).
# - Upload extra Q&A (CSV/JSON/TXT) to extend answers.
# - Q&A answers are searched first (fuzzy match), then symptom/medicine logic.
# - Cleaner dark UI, animated header, subtle button hovers, and celebration balloons.
# - No external APIs. Only depends on Streamlit.

import re, csv, io, json, os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional
from difflib import SequenceMatcher

import streamlit as st

# -------------------------
# Page config + Styles
# -------------------------
st.set_page_config(page_title="Personalised Medicines Chatbot", page_icon="💊", layout="wide")

CSS = """
<style>
:root { --bg:#0f1116; --panel:#171a22; --muted:#9aa3b2; --brand:#76e4f7; --accent:#7c3aed; }
main .block-container {padding-top: 1.5rem;}

/* Animated gradient title bar */
.hero {border-radius:20px;padding:22px 26px;margin-bottom:18px;background:linear-gradient(120deg,#111827, #1f2937,#0f172a);
  background-size:200% 200%; animation:gradmove 8s ease infinite; box-shadow:0 8px 30px rgba(0,0,0,.25)}
.hero h1 {margin:0;font-size:34px;letter-spacing:.3px}
.hero p {margin:.25rem 0 0;color:var(--muted)}
@keyframes gradmove {0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}

/* Badges */
.badge {display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:700;margin-right:6px}
.badge-red {background:#fee2e2;color:#991b1b;border:1px solid #fecaca}
.badge-yellow {background:#fef9c3;color:#854d0e;border:1px solid #fde68a}
.badge-blue {background:#dbeafe;color:#1e40af;border:1px solid #bfdbfe}

/* Cards */
.card {background:var(--panel);border:1px solid #232836;border-radius:18px;padding:16px;margin:8px 0;box-shadow:0 4px 16px rgba(0,0,0,.15)}

/* Buttons hover */
.stButton>button {border-radius:12px;border:1px solid #2b3242;padding:.5rem 1rem;transition:transform .06s ease, box-shadow .2s ease}
.stButton>button:hover {transform:translateY(-1px);box-shadow:0 10px 24px rgba(124,58,237,.25)}

/* Chat input rounder */
[data-baseweb="textarea"] textarea {border-radius:12px!important}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

st.markdown(
    """
<div class="hero">
  <h1>💊 Personalised Medicines Chatbot</h1>
  <p>Fast answers from your Q&A + safe, local symptom/medicine guidance.</p>
</div>
""",
    unsafe_allow_html=True,
)

# -------------------------
# Built‑in Knowledge Base (simplified)
# -------------------------
KB: Dict[str, Dict[str, Any]] = {
    "paracetamol": {
        "aliases": ["paracetamol", "acetaminophen", "pcm", "crocin"],
        "class": "Analgesic/antipyretic",
        "adult_dose": "500 mg every 6–8 hours as needed; do not exceed 3,000 mg/day.",
        "notes": "Avoid combining with other acetaminophen‑containing products.",
        "contraindications": ["severe_liver_disease"],
        "cautions": ["liver_disease", "alcohol_use"],
    },
    "ibuprofen": {
        "aliases": ["ibuprofen", "brufen", "advil"],
        "class": "NSAID",
        "adult_dose": "200–400 mg every 6–8 hours **after food**; max 1,200 mg/day.",
        "notes": "May irritate stomach; avoid in active ulcers.",
        "contraindications": ["active_ulcer", "severe_kidney_disease"],
        "cautions": ["asthma", "gastritis"],
    },
    "cetirizine": {
        "aliases": ["cetirizine", "cetzine", "zyrtec"],
        "class": "Antihistamine",
        "adult_dose": "10 mg once daily (may cause drowsiness).",
        "notes": "Avoid driving/operating machinery if drowsy.",
        "contraindications": [],
        "cautions": ["alcohol_use"],
    },
    "omeprazole": {
        "aliases": ["omeprazole", "omez", "prilosec"],
        "class": "Proton pump inhibitor",
        "adult_dose": "20 mg once daily before breakfast for 7–14 days.",
        "notes": "Seek care if alarm features (bleeding, black stools, severe pain).",
        "contraindications": [],
        "cautions": [],
    },
    "ors": {
        "aliases": ["ors", "oral rehydration", "oral rehydration salts"],
        "class": "Rehydration solution",
        "adult_dose": "Small frequent sips; ~200–250 ml after each loose stool.",
        "notes": "Use WHO‑ORS; avoid sugary sodas.",
        "contraindications": [],
        "cautions": [],
    },
}
SUPPORTED = list(KB.keys())

CONDITION_PATTERNS = {
    "headache": [r"\bheadache\b", r"\bmigraine\b", r"sir\s*dard"],
    "fever": [r"\bfever\b", r"\bbukhar\b"],
    "cold_cough": [r"\bcold\b", r"\bcough\b", r"runny\s*nose", r"khansi"],
    "allergy": [r"\ballergy\b", r"\bsneeze\b", r"\bitch\b", r"rhinitis"],
    "acidity": [r"\bacidity\b", r"heartburn", r"acid\s*reflux", r"gastritis"],
    "diarrhea": [r"\bdiarrhea\b", r"loose\s*motions"],
}

# -------------------------
# Built‑in Q&A from your dataset
# -------------------------
DEFAULT_QNA = [
    # Diabetes
    {"q":"What are the early signs of diabetes?","a":"Excess thirst/urination, fatigue, blurry vision, slow‑healing wounds, unexplained weight loss."},
    {"q":"How is diabetes diagnosed?","a":"Fasting glucose ≥126 mg/dL, A1c ≥6.5%, random glucose ≥200 mg/dL with symptoms, or failed oral glucose tolerance."},
    {"q":"What’s a good A1c target?","a":"Most adults: <7%. Older/complex patients may aim a bit higher; individualize with a doctor."},
    {"q":"Do I need medicine or can diet fix it?","a":"Type 2: start with diet/exercise; metformin is first‑line if targets aren’t met. Type 1 always needs insulin."},
    {"q":"What should I eat?","a":"High fiber, lean protein, non‑starchy veggies; limit refined carbs/sugary drinks; consistent portions; track carbs."},
    {"q":"How often should I check sugar?","a":"On insulin: multiple times daily or use CGM. On pills/stable: at least a few times/week and before key changes."},
    {"q":"What to do for low sugar (hypo)?","a":"If <70 mg/dL or symptoms: take 15 g fast carbs (glucose tabs/juice), recheck in 15 min, repeat if needed."},
    {"q":"High sugar?","a":"Hydrate, walk (if no ketones/illness), check ketones if >250 mg/dL, adjust per plan, call doctor if persistent."},
    {"q":"Must‑have yearly checks?","a":"Eyes (retina), kidney (urine albumin), feet/neuropathy, lipids, blood pressure, vaccines."},
    {"q":"Can diabetes be reversed?","a":"Type 2: remission possible with weight loss, diet, and activity (not guaranteed). Type 1: cannot be reversed."},
    # Cancer
    {"q":"What are general red flags?","a":"Unintentional weight loss, persistent pain, new lumps, abnormal bleeding, non‑healing sores, cough/voice change >3 weeks."},
    {"q":"How is cancer confirmed?","a":"Biopsy. Imaging suggests; pathology proves."},
    {"q":"What does stage mean?","a":"Extent of spread (size, nodes, metastasis). Stage drives treatment and prognosis."},
    {"q":"Do all cancers need chemo?","a":"No. Some need surgery only; others get radiation, targeted therapy, immunotherapy, or combinations."},
    {"q":"Are chemo side effects inevitable?","a":"Common (fatigue, nausea, hair loss), but modern anti‑nausea and supportive meds reduce them significantly."},
    {"q":"Should I take supplements during treatment?","a":"Don’t start anything without oncologist approval — some interact and blunt treatment."},
    {"q":"Is screening actually useful?","a":"Yes — colon, breast, cervical, and high‑risk lung screenings cut deaths when done on schedule."},
    {"q":"Can lifestyle affect outcomes?","a":"Yes. No tobacco/alcohol moderation, exercise, weight control, and good sleep improve tolerance and survival odds."},
    # Abdominal Ultrasound
    {"q":"What is an abdominal ultrasound?","a":"A non‑invasive test using high‑frequency sound waves to image abdominal organs (liver, kidneys, pancreas, gallbladder, spleen, aorta)."},
    {"q":"Why is an abdominal ultrasound done?","a":"To evaluate pain, swelling, abnormal labs, liver disease, gallstones/kidney stones, tumors, or internal bleeding after trauma."},
    {"q":"Is abdominal ultrasound safe?","a":"Yes. No radiation; painless; no known side effects when performed correctly."},
    {"q":"How should I prepare for an abdominal ultrasound?","a":"Usually fast 8 hours to keep stomach empty and reduce gas; sometimes arrive with full bladder if instructed."},
    {"q":"What happens during the procedure?","a":"You lie down; gel applied; a probe is moved over the abdomen to capture images on a screen."},
    {"q":"How long does the test take?","a":"About 20–30 minutes depending on how many organs are examined."},
    {"q":"Does it hurt?","a":"No. It’s painless, though you may feel mild pressure or cool gel."},
    {"q":"What problems can an abdominal ultrasound detect?","a":"Cirrhosis, gallstones, kidney stones, tumors/cysts, fluid, blocked bile ducts, enlarged organs, abdominal aortic aneurysm."},
    {"q":"Are there limitations to this test?","a":"Gas/obesity can reduce image quality; intestines and bone are harder to see. CT/MRI may be needed for more detail."},
    {"q":"What do normal and abnormal results mean?","a":"Normal: organs look healthy; Abnormal: stones, cysts, tumors, infection, organ damage, or bleeding — may need further tests/treatment."},
]

# -------------------------
# Profile model
# -------------------------
@dataclass
class Profile:
    age: Optional[int] = 25
    sex: str = "female"
    weight_kg: Optional[float] = 60.0
    conditions: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    meds: List[str] = field(default_factory=list)

# -------------------------
# Helpers
# -------------------------

def normalize(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip().lower())

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", s.lower()).strip()

def _sim(a: str, b: str) -> float:
    at, bt = set(_norm(a).split()), set(_norm(b).split())
    jacc = (len(at & bt) / len(at | bt)) if (at | bt) else 0.0
    seq = SequenceMatcher(None, _norm(a), _norm(b)).ratio()
    return 0.6 * jacc + 0.4 * seq

# Robust file loader for uploaded Q&A

def load_qna_file(file) -> List[Dict[str,str]]:
    raw = file.read()
    text = None
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            text = raw.decode(enc) if isinstance(raw, bytes) else raw
            if isinstance(text, bytes):
                text = text.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        return []

    name = file.name.lower(); data: List[Dict[str,str]] = []
    Q = {"question","q","query","prompt"}
    A = {"answer","a","ans","response","reply"}

    if name.endswith(".csv"):
        try:
            sn = csv.Sniffer(); dialect = sn.sniff(text.splitlines()[0])
        except Exception:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(text), dialect)
        rows = list(reader)
        if not rows: return []
        header = [c.strip().lower() for c in rows[0]]
        q_idx = a_idx = None
        if any(h in Q for h in header) and any(h in A for h in header):
            for i,h in enumerate(header):
                if h in Q: q_idx = i
                if h in A: a_idx = i
            body = rows[1:]
        else:
            q_idx, a_idx, body = 0, 1, rows
        for r in body:
            if len(r) > max(q_idx, a_idx):
                q = (r[q_idx] or "").strip(); a=(r[a_idx] or "").strip()
                if q and a: data.append({"q":q,"a":a,"src":file.name})

    elif name.endswith(".json"):
        try:
            obj = json.loads(text)
            for it in obj:
                q = (it.get("question") or it.get("q") or it.get("query") or "").strip()
                a = (it.get("answer") or it.get("a") or it.get("response") or "").strip()
                if q and a: data.append({"q":q,"a":a,"src":file.name})
        except Exception:
            return []

    elif name.endswith(".txt"):
        for line in text.splitlines():
            line=line.strip()
            if not line: continue
            if ":::" in line:
                q,a = line.split(":::",1)
            elif "," in line:
                q,a = line.split(",",1)
            else:
                continue
            q,a = q.strip(), a.strip()
            if q and a: data.append({"q":q,"a":a,"src":file.name})

    return data

# Q&A retrieval

def best_qna_answer(query: str, base: List[Dict[str,str]], k:int=3, min_score:float=0.5):
    if not base: return None
    scored = [( _sim(query, item["q"]), item ) for item in base]
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [ (round(s,3), i) for s,i in scored[:k] if s >= min_score ]
    if not top: return None
    best_s, best_item = top[0]
    if len(top)==1 or (len(top)>1 and best_s - top[1][0] >= 0.1):
        return {"mode":"single","answer":best_item["a"],"score":best_s,"q":best_item["q"],"src":best_item.get("src","builtin")}
    else:
        return {"mode":"multi","candidates":[{"q":i["q"],"a":i["a"],"score":s,"src":i.get("src","builtin")} for s,i in top]}

# Medicine logic

def find_drug(user_text: str) -> Tuple[str, Dict[str, Any]]:
    t = normalize(user_text)
    for key, info in KB.items():
        for alias in info["aliases"]:
            if alias in t:
                return key, info
    for key in KB.keys():
        if key in t:
            return key, KB[key]
    return "", {}


def check_profile_vs_drug(profile: "Profile", drug_key: str) -> Dict[str, Any]:
    info = KB[drug_key]
    flags = []
    for c in info.get("contraindications", []):
        if c in profile.conditions or c in profile.allergies:
            flags.append({"type":"contraindication","detail":c})
    for c in info.get("cautions", []):
        if c in profile.conditions or c in profile.allergies or c in profile.meds:
            flags.append({"type":"caution","detail":c})
    return {"flags": flags}


def render_flags(flags: List[Dict[str,str]]):
    contra, caution = [], []
    for f in flags:
        if f["type"]=="contraindication": contra.append(f["detail"])
        if f["type"]=="caution": caution.append(f["detail"])
    return contra, caution

# Condition guidance (short classroom advice)

def condition_plan(cond: str) -> Dict[str, Any]:
    plan = {"title": cond.replace('_',' ').title(), "regimen": [], "notes": [], "red_flags": []}
    if cond == "headache":
        plan["regimen"] += [
            "Paracetamol 500 mg morning & night; may add midday dose if needed (max 3,000 mg/day).",
            "If not enough: Ibuprofen 200–400 mg after food, up to every 6–8 h (max 1,200 mg/day).",
        ]
        plan["red_flags"] += ["worst‑ever headache", "head injury", "fever + neck stiffness", "neurologic deficits"]
    elif cond == "fever":
        plan["regimen"].append("Paracetamol 500 mg every 6–8 h as needed (max 3,000 mg/day).")
    elif cond == "cold_cough":
        plan["regimen"] += [
            "Steam/warm fluids; honey for throat (>1y).",
            "Dry cough: Dextromethorphan 10–20 mg every 4–6 h.",
            "Runny/itchy nose: Cetirizine 10 mg at night.",
        ]
    elif cond == "allergy":
        plan["regimen"].append("Cetirizine 10 mg once daily (prefer night).")
    elif cond == "acidity":
        plan["regimen"].append("Omeprazole 20 mg once daily before breakfast for 7–14 days.")
    elif cond == "diarrhea":
        plan["regimen"].append("WHO‑ORS ~200–250 ml after each loose stool; frequent sips.")
    else:
        plan["notes"].append("No plan available.")
    return plan

# -------------------------
# Sidebar — Profile & Q&A Upload
# -------------------------
if "profile" not in st.session_state:
    st.session_state.profile = Profile()
if "custom_qna" not in st.session_state:
    st.session_state.custom_qna = []

p: Profile = st.session_state.profile

st.sidebar.header("Your Profile")
col1, col2 = st.sidebar.columns(2)
with col1:
    p.age = st.number_input("Age (years)", 0, 120, int(p.age or 25), step=1)
with col2:
    p.sex = st.selectbox("Sex", ["female","male","other"], index=["female","male","other"].index(p.sex))

p.weight_kg = st.sidebar.number_input("Weight (kg)", 3.0, 300.0, float(p.weight_kg or 60.0), step=0.5)

st.sidebar.subheader("Conditions (tick if apply)")
opts = [
    ("severe_liver_disease", "Severe liver disease"),
    ("liver_disease", "Liver disease (any)"),
    ("severe_kidney_disease", "Severe kidney disease"),
    ("active_ulcer", "Active stomach/duodenal ulcer"),
    ("gastritis", "Gastritis / acid reflux"),
    ("asthma", "Asthma"),
    ("alcohol_use", "Regular alcohol use"),
]
sel = []
for key, label in opts:
    if st.sidebar.checkbox(label, value=(key in p.conditions)):
        sel.append(key)
p.conditions = sel

st.sidebar.subheader("Allergies (comma separated)")
allergy_str = st.sidebar.text_input("e.g., penicillin, sulfa", ", ".join(p.allergies))
p.allergies = [a.strip().lower().replace(" ", "_") for a in allergy_str.split(",") if a.strip()]

st.sidebar.subheader("Current regular meds (comma separated)")
meds_str = st.sidebar.text_input("e.g., blood_thinners, metformin", ", ".join(p.meds))
p.meds = [m.strip().lower().replace(" ", "_") for m in meds_str.split(",") if m.strip()]

if st.sidebar.button("Send details"):
    st.balloons()
    recap = (
        f"**Profile received**\n"
        f"Age/Sex: {p.age} / {p.sex}  \n"
        f"Weight: {p.weight_kg} kg  \n"
        f"Conditions: {', '.join(p.conditions) if p.conditions else '—'}  \n"
        f"Allergies: {', '.join(p.allergies) if p.allergies else '—'}  \n"
        f"Current meds: {', '.join(p.meds) if p.meds else '—'}"
    )
    if "history" not in st.session_state: st.session_state.history=[]
    st.session_state.history.append(("assistant", recap))

st.sidebar.header("Upload your Q&A file")
qna_files = st.sidebar.file_uploader(
    "CSV (question,answer), JSON list, or TXT (question ::: answer)",
    type=["csv","json","txt"], accept_multiple_files=True
)
if qna_files:
    qna_all=[]
    for f in qna_files:
        qna_all += load_qna_file(f)
    # merge with existing + builtin
    merged = DEFAULT_QNA + st.session_state.custom_qna + qna_all
    # dedup by normalized question
    seen=set(); dedup=[]
    for item in merged:
        k=_norm(item["q"]) if isinstance(item,dict) else _norm(item.get("q",""))
        if k and k not in seen:
            seen.add(k); dedup.append(item)
    st.session_state.custom_qna = dedup

count = len(st.session_state.custom_qna) or len(DEFAULT_QNA)
if count>0:
    st.sidebar.caption(f"Loaded Q&A: {len(st.session_state.custom_qna) or len(DEFAULT_QNA)} items")
    with st.sidebar.expander("Preview first 3"):
        src = st.session_state.custom_qna or DEFAULT_QNA
        for item in src[:3]:
            st.write("Q:", item["q"]) ; st.write("A:", item["a"]) ; st.write("---")
else:
    st.sidebar.warning("Loaded Q&A: 0 items — add CSV/JSON/TXT or rely on built‑in set.")

# -------------------------
# Chat state + Greeting
# -------------------------
if "history" not in st.session_state:
    st.session_state.history = []
if "greeted" not in st.session_state:
    st.session_state.greeted = False

if not st.session_state.greeted and len(st.session_state.history)==0:
    greet = (
        "Hi! I can answer from your Q&A first. Ask me: *What are the early signs of diabetes?*\n\n"
        "You can also ask symptoms like *headache* or a medicine like *paracetamol*."
    )
    st.session_state.history.append(("assistant", greet))
    st.session_state.greeted = True

# Render history
for role, text in st.session_state.history:
    with st.chat_message(role): st.markdown(text, unsafe_allow_html=True)

# -------------------------
# Chat input and core flow
# -------------------------
prompt = st.chat_input("Type your question… (e.g., 'What is an abdominal ultrasound?')")


def _reply(text: str):
    st.session_state.history.append(("assistant", text))
    with st.chat_message("assistant"):
        st.markdown(text, unsafe_allow_html=True)

if prompt:
    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"): st.markdown(prompt)

    # 0) Q&A (custom then built‑in)
    base = st.session_state.custom_qna if st.session_state.custom_qna else DEFAULT_QNA
    ans = best_qna_answer(prompt, base)
    if ans:
        if ans["mode"]=="single":
            _reply(ans["answer"] + f"\n\n> From Q&A (match: {ans['score']}, source: {ans.get('src','builtin')})")
        else:
            lines=["I found related entries in your Q&A:"]
            for c in ans["candidates"]:
                lines.append(f"- **Q:** {c['q']}\n  **A:** {c['a']} _(match {c['score']}, src: {c.get('src','builtin')})_")
            _reply("\n".join(lines))
    else:
        # 1) Greeting intent
        t = normalize(prompt)
        if re.search(r"\b(hi|hello|hey|namaste|good\s*(morning|evening|afternoon))\b", t):
            _reply("Hello! Tell me your main problem — or upload a Q&A file and ask me from that.")
        else:
            # 2) Condition intent
            cond=""
            for c, pats in CONDITION_PATTERNS.items():
                if any(re.search(p, t) for p in pats):
                    cond=c; break
            if cond:
                plan = condition_plan(cond)
                # safety badges if plan mentions medicines
                flags=[]
                text=" ".join(plan.get("regimen", []))
                for dk in SUPPORTED:
                    if any(a in text.lower() for a in KB[dk]["aliases"]):
                        flags += check_profile_vs_drug(p, dk)["flags"]
                contra, caution = render_flags(flags)
                parts=[f"**Problem:** {plan['title']}"]
                if plan.get("regimen"):
                    parts.append("\n**Suggested:**")
                    parts += [f"• {r}" for r in plan["regimen"]]
                if contra or caution:
                    badges=[]
                    if contra: badges.append(f"<span class='badge badge-red'>Contra: {', '.join(sorted(set(contra)))}</span>")
                    if caution: badges.append(f"<span class='badge badge-yellow'>Caution: {', '.join(sorted(set(caution)))}</span>")
                    parts.append("\n"+" ".join(badges))
                _reply("\n".join(parts))
            else:
                # 3) Medicine intent
                med_key, info = find_drug(t)
                if med_key:
                    checks = check_profile_vs_drug(p, med_key)
                    contra, caution = render_flags(checks["flags"])
                    lines=[
                        f"**Medicine:** {med_key.title()}",
                        f"**Class:** {info['class']}",
                        "",
                        f"**Dose:** {info['adult_dose']}",
                        f"**Notes:** {info['notes']}",
                    ]
                    if contra or caution:
                        lines.append("")
                        if contra: lines.append("Contra: " + ", ".join(sorted(set(contra))))
                        if caution: lines.append("Caution: " + ", ".join(sorted(set(caution))))
                    _reply("\n".join(lines))
                else:
                    _reply("Sorry, I'm not trained on that. Try uploading Q&A or ask a common complaint/medicine.")

st.caption("© Minor Project — Offline, explainable chatbot. UI: animated header, badges, balloons.")

import json, os, glob, datetime

BASE = "/Users/anshullkgarg/Desktop/projects/claude-gpt/uber-interviews"
RAW = os.path.join(BASE, "raw")

def categorize(name):
    n = (name or "").lower()
    if "low-level" in n or "low level" in n or "lld" in n: return "Low-Level Design (LLD)"
    if "high-level" in n or "high level" in n or "hld" in n or "system design" in n: return "System Design (HLD)"
    if "machine coding" in n: return "Machine Coding"
    if "hiring manager" in n or "managerial" in n or ("manager" in n): return "Hiring Manager / Managerial"
    if "behaviou" in n or "behavio" in n or "culture" in n or "bar raiser" in n or "leadership" in n or "values" in n: return "Behavioral / Culture"
    if "online" in n or "screening" in n or "phone screen" in n or "screen" in n or "assessment" in n or n.strip()=="oa": return "Screening / Online Assessment"
    if "dsa" in n or "coding" in n or "problem solving" in n or "problem-solving" in n or "algorithm" in n or "data structure" in n: return "DSA / Coding"
    return "Other"

experiences = []
questions = []

for f in sorted(glob.glob(RAW + "/*.json"), key=lambda p: -int(os.path.basename(p)[:-5])):
    d = json.load(open(f))
    eid = d["id"]
    role = d["designation"]["title"]
    exp_meta = {
        "id": eid,
        "role": role,
        "roleDomain": d.get("roleDomain"),
        "level": d.get("level"),
        "yoe": d.get("yearsOfExperience"),
        "receivedOffer": d.get("receivedOffer"),
        "isAnon": d.get("isAnon"),
        "interviewDate": d.get("interviewDate"),
        "roundsCount": d.get("roundsCount"),
        "questionsCount": d.get("questionsCount"),
        "url": d.get("url"),
        "generalNotes": d.get("generalNotes"),
        "preparationStrategy": d.get("preparationStrategy"),
        "rounds": [],
    }
    for r in (d.get("rounds") or []):
        rnum = r.get("number")
        rname = (r.get("name") or "").strip()
        cat = categorize(rname)
        exp_meta["rounds"].append({"number": rnum, "name": rname, "category": cat,
                                   "desc": r.get("roundDescription"), "durationDl": r.get("durationDl")})
        for qe in (r.get("questions") or []):
            qq = qe.get("question") or {}
            questions.append({
                "qid": qq.get("id"),
                "title": qq.get("title") or "(untitled)",
                "statement": qq.get("statement") or "",
                "difficulty": (qq.get("difficulty") or "NA"),
                "topics": [t.get("dl") for t in (qq.get("topics") or []) if t.get("dl")],
                "qurl": qq.get("url"),
                "answerSummary": qe.get("candidateAnswerSummary"),
                "roundNumber": rnum,
                "roundName": rname,
                "roundCategory": cat,
                "expId": eid,
                "role": role,
                "roleDomain": d.get("roleDomain"),
                "level": d.get("level"),
                "expUrl": d.get("url"),
                "interviewDate": d.get("interviewDate"),
                "receivedOffer": d.get("receivedOffer"),
            })
    experiences.append(exp_meta)

payload = {
    "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    "company": "Uber",
    "experiences": experiences,
    "questions": questions,
    "stats": {
        "experiences": len(experiences),
        "questions": len(questions),
        "rounds": sum(len(e["rounds"]) for e in experiences),
    },
}

with open(os.path.join(BASE, "data.json"), "w") as f:
    json.dump(payload, f, ensure_ascii=False)
print("experiences:", len(experiences), "questions:", len(questions),
      "rounds:", payload["stats"]["rounds"])

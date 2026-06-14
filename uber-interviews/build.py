import datetime
import glob
import json
import os
import re

BASE = "/Users/anshullkgarg/Desktop/projects/claude-gpt/uber-interviews"
RAW = os.path.join(BASE, "raw")
RAW_LC = os.path.join(BASE, "raw_leetcode")
RAW_LC2 = os.path.join(BASE, "raw_leetcode_v2")


def normalize_role(raw):
    """Collapse free-form role titles from both sources into one canonical set."""
    t = (raw or "").lower()
    if not t.strip(): return "Unspecified"
    if "test" in t or "sdet" in t: return "SDET"
    if "data engineer" in t: return "Data Engineer"
    if re.search(r"machine learning|\bmle?\b|data scien|\bai\b", t): return "ML / Data Science"
    if re.search(r"front[\s\-]?end|\breact\b|web dev", t): return "Frontend Engineer"
    if re.search(r"android|\bios\b|mobile", t): return "Mobile Engineer"
    if re.search(r"engineering manager|\bem\b", t): return "Engineering Manager"
    if re.search(r"intern", t): return "SDE 1 / New Grad"
    if re.search(r"\b(?:sde|se|swe)[\s\-]*(?:4|iv)\b|engineer[\s\-]*4\b|staff|principal|\bl5b\b|\bl6\b", t): return "Staff / SDE 4"
    if re.search(r"\b(?:sde|se|swe)[\s\-]*(?:3|iii)\b|engineer[\s\-]*3\b|senior|\bsr\.?\b|\bsse\b|\bl5a?\b", t): return "Senior / SDE 3"
    if re.search(r"\b(?:sde|se|swe)[\s\-]*(?:2|ii)\b|engineer[\s\-]*2\b|\bl4\b", t): return "SDE 2"
    if re.search(r"\b(?:sde|se|swe)[\s\-]*(?:1|i)\b|engineer[\s\-]*1\b|new grad|graduate|\bl3\b", t): return "SDE 1 / New Grad"
    if re.search(r"\bsde\b|software engineer|\bswe\b|developer|backend|back[\s\-]?end", t): return "Software Engineer"
    return "Unspecified"


def categorize(name):
    n = (name or "").lower()
    if "low-level" in n or "low level" in n or "lld" in n: return "Low-Level Design (LLD)"
    if "high-level" in n or "high level" in n or "hld" in n or "system design" in n: return "System Design (HLD)"
    if "machine coding" in n: return "Machine Coding"
    if "hiring manager" in n or "managerial" in n or ("manager" in n): return "Hiring Manager / Managerial"
    if "behaviou" in n or "behavio" in n or "culture" in n or "bar raiser" in n or "leadership" in n or "values" in n: return "Behavioral / Culture"
    if "online" in n or "screening" in n or "phone screen" in n or "screen" in n or "assessment" in n or n.strip() == "oa": return "Screening / Online Assessment"
    if "dsa" in n or "coding" in n or "problem solving" in n or "problem-solving" in n or "algorithm" in n or "data structure" in n: return "DSA / Coding"
    return "Other"


# ---------------------------------------------------------------- enginebogie
experiences = []
questions = []

for f in sorted(glob.glob(RAW + "/*.json"), key=lambda p: -int(os.path.basename(p)[:-5])):
    d = json.load(open(f))
    eid = d["id"]
    role_raw = d["designation"]["title"]
    role = normalize_role(role_raw)
    exp_meta = {
        "id": eid,
        "role": role_raw,
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
                "source": "enginebogie",
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
                "roleRaw": role_raw,
                "roleDomain": d.get("roleDomain"),
                "level": d.get("level"),
                "expUrl": d.get("url"),
                "interviewDate": d.get("interviewDate"),
                "receivedOffer": d.get("receivedOffer"),
            })
    experiences.append(exp_meta)


# ---------------------------------------------------------------- leetcode
def lc_clean(text):
    """LeetCode discuss API ships markdown with literal \\n / \\t sequences."""
    if not text:
        return ""
    return text.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')


def lc_categorize(title, category):
    t = (title or "").lower()
    if re.search(r"system design|\bhld\b|high[\s-]level", t): return "System Design (HLD)"
    if re.search(r"\blld\b|low[\s-]level|machine coding|\bood\b|object[\s-]oriented", t): return "Low-Level Design (LLD)"
    if re.search(r"hiring manager|\bhm\b|managerial", t): return "Hiring Manager / Managerial"
    if re.search(r"behaviou?r|bar raiser|leadership|culture", t): return "Behavioral / Culture"
    if re.search(r"\boa\b|online assessment|online test|codesignal|hackerrank|karat", t): return "Screening / Online Assessment"
    if re.search(r"phone screen|phone interview|screening|recruiter", t): return "Screening / Online Assessment"
    if re.search(r"\bdsa\b|onsite|on-site|coding|algorithm|virtual", t): return "DSA / Coding"
    if category == "interview-experience": return "Interview Experience"
    return "DSA / Coding"


leetcode_count = 0
skipped_offtopic = 0
for f in sorted(glob.glob(RAW_LC + "/*.json"), key=lambda p: -int(os.path.basename(p)[:-5])):
    d = json.load(open(f))
    topic = d.get("topic") or {}
    post = topic.get("post") or {}
    node = d.get("node") or {}
    tid = topic.get("id") or node.get("id")
    title = (topic.get("title") or "").strip() or "(untitled)"
    content = lc_clean(post.get("content"))
    # tag search returns some cross-company posts; keep only ones that mention
    # Uber in the title or in the prose (links to uber threads don't count)
    content_prose = re.sub(r"https?://\S+", " ", content.lower())
    if "uber" not in title.lower() and "uber" not in content_prose:
        skipped_offtopic += 1
        continue
    created = post.get("creationDate")
    author = (post.get("author") or {}).get("username")
    comments = []
    for c in (d.get("comments") or []):
        cp = c.get("post") or {}
        body = lc_clean(cp.get("content"))
        if not body.strip():
            continue
        comments.append({
            "author": (cp.get("author") or {}).get("username"),
            "votes": cp.get("voteCount") or 0,
            "content": body,
        })
    comments.sort(key=lambda c: -c["votes"])
    questions.append({
        "qid": f"lc{tid}",
        "source": "leetcode",
        "title": title,
        "statement": content,
        "difficulty": "NA",
        "topics": [],
        "qurl": f"https://leetcode.com/discuss/post/{tid}/",
        "answerSummary": None,
        "comments": comments[:6],
        "votes": post.get("voteCount") or 0,
        "views": topic.get("viewCount") or node.get("viewCount") or 0,
        "commentCount": node.get("commentCount") or 0,
        "author": author,
        "roundNumber": None,
        "roundName": None,
        "roundCategory": lc_categorize(title, d.get("category")),
        "expId": None,
        "role": normalize_role(title),
        "roleRaw": None,
        "roleDomain": None,
        "level": None,
        "expUrl": None,
        "interviewDate": created * 1000 if created else None,
        "receivedOffer": None,
    })
    leetcode_count += 1

# -------------------------------------------- leetcode (new article system)
seen_lc = {q["qid"] for q in questions if q["source"] == "leetcode"}
for f in sorted(glob.glob(RAW_LC2 + "/*.json"), key=lambda p: -int(os.path.basename(p)[:-5])):
    d = json.load(open(f))
    node = d.get("node") or {}
    a = d.get("article") or {}
    tid = node.get("topicId")
    qid = f"lc{tid}"
    if qid in seen_lc:
        continue
    title = (a.get("title") or "").strip() or "(untitled)"
    content = a.get("content") or ""  # v2 content has real newlines
    content_prose = re.sub(r"https?://\S+", " ", content.lower())
    if "uber" not in title.lower() and "uber" not in content_prose:
        skipped_offtopic += 1
        continue
    created_ms = None
    if a.get("createdAt"):
        created_ms = int(datetime.datetime.fromisoformat(a["createdAt"]).timestamp() * 1000)
    votes = sum((r.get("count") or 0) for r in (a.get("reactions") or []))
    comments = []
    for c in (d.get("comments") or []):
        cp = c.get("post") or {}
        body = lc_clean(cp.get("content"))
        if not body.strip():
            continue
        comments.append({
            "author": (cp.get("author") or {}).get("username"),
            "votes": cp.get("voteCount") or 0,
            "content": body,
        })
    comments.sort(key=lambda c: -c["votes"])
    questions.append({
        "qid": qid,
        "source": "leetcode",
        "title": title,
        "statement": content,
        "difficulty": "NA",
        "topics": [],
        "qurl": f"https://leetcode.com/discuss/post/{tid}/{node.get('slug') or ''}/",
        "answerSummary": None,
        "comments": comments[:6],
        "votes": votes,
        "views": a.get("hitCount") or node.get("hitCount") or 0,
        "commentCount": (node.get("topic") or {}).get("commentCount") or 0,
        "author": (a.get("author") or {}).get("userSlug"),
        "roundNumber": None,
        "roundName": None,
        "roundCategory": lc_categorize(title, "interview-question"),
        "expId": None,
        "role": normalize_role(title),
        "roleRaw": None,
        "roleDomain": None,
        "level": None,
        "expUrl": None,
        "interviewDate": created_ms,
        "receivedOffer": None,
    })
    leetcode_count += 1

payload = {
    "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    "company": "Uber",
    "experiences": experiences,
    "questions": questions,
    "stats": {
        "experiences": len(experiences),
        "questions": len(questions),
        "rounds": sum(len(e["rounds"]) for e in experiences),
        "leetcodePosts": leetcode_count,
    },
}

with open(os.path.join(BASE, "data.json"), "w") as f:
    json.dump(payload, f, ensure_ascii=False)
print("experiences:", len(experiences),
      "| enginebogie questions:", len(questions) - leetcode_count,
      "| leetcode posts:", leetcode_count,
      "| skipped off-topic:", skipped_offtopic,
      "| rounds:", payload["stats"]["rounds"])

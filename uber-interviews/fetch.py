import json, os, time, urllib.request

BASE = "/Users/anshullkgarg/Desktop/projects/claude-gpt/uber-interviews"
RAW = os.path.join(BASE, "raw")
os.makedirs(RAW, exist_ok=True)

def get(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/json, text/plain, */*",
        "x-user-tz": "+05:30",
        "Referer": "https://enginebogie.com/interview/experiences",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

search = json.load(open(os.path.join(BASE, "search_uber.json")))
ids = [c["id"] for c in search["content"]]
print("total ids:", len(ids))

ok = 0
for i, eid in enumerate(ids):
    dest = os.path.join(RAW, f"{eid}.json")
    if os.path.exists(dest) and os.path.getsize(dest) > 100:
        ok += 1
        continue
    try:
        data = get(f"https://enginebogie.com/api/interview/experience/{eid}")
        # validate JSON
        json.loads(data)
        with open(dest, "wb") as f:
            f.write(data)
        ok += 1
        print(f"[{i+1}/{len(ids)}] {eid} ok ({len(data)} bytes)")
        time.sleep(0.3)
    except Exception as e:
        print(f"[{i+1}/{len(ids)}] {eid} FAILED: {e}")

print("done. saved:", ok, "/", len(ids))

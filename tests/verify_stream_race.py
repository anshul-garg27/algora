from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page()
    errs=[]; pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
    pg.goto("http://127.0.0.1:8013", wait_until="networkidle"); pg.wait_for_timeout(400)
    # Simulate the EXACT streaming race: opener text, then a tool BEFORE the rAF fires.
    res = pg.evaluate("""() => {
      const tab = tabs[active];
      startAssistantTurn(tab);
      handleEvent(tab, {type:'text_delta', text:'## 1. Problem Understanding\\nA\\n\\n## 2. Understand It On Paper\\nB\\n\\n## 3. Approach & Intuition\\nC\\n\\n## 4. Brute Force\\nD\\n\\n## 5. Optimal Approach\\nE\\n'});
      handleEvent(tab, {type:'tool_call', id:'t1', name:'run_python', input:{path:'x.py'}});   // race: before rAF
      handleEvent(tab, {type:'tool_result', id:'t1', name:'run_python', output:'ok', is_error:false});
      handleEvent(tab, {type:'text_delta', text:'## 6. Solution\\nF\\n\\n## 7. Code Walkthrough\\nG\\n\\n## 8. Complexity Analysis\\nH\\n\\n## 9. Edge Cases\\nI\\n'});
      handleEvent(tab, {type:'tool_call', id:'t2', name:'run_python', input:{path:'y.py'}});
      handleEvent(tab, {type:'tool_result', id:'t2', name:'run_python', output:'ok', is_error:false});
      handleEvent(tab, {type:'turn_done', stop_reason:'end_turn'});
      return tab.turn.body.innerText;
    }""")
    headers = ["Problem Understanding","Understand It On Paper","Approach & Intuition","Brute Force","Optimal Approach","Solution","Code Walkthrough","Complexity Analysis","Edge Cases"]
    present = [h for h in headers if h in res]
    print("sections rendered in LIVE view:", len(present), "/ 9")
    print("missing:", [h for h in headers if h not in res] or "NONE ✅")
    print("console errors:", errs[:3] if errs else "none")
    b.close()

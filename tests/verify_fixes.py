"""Verify the bug fixes in a real browser:
1. Glued one-line Markdown table now renders as a table.
2. XSS link payload cannot inject event-handler attributes.
3. A real streaming interview run keeps its Mermaid diagram (rAF-race fix).
Server must be up on :8000.
"""

import sys
from playwright.sync_api import sync_playwright

GLUED = "| Approach | Complexity | Reason | |---|---|---| | Brute Force | O(2^n) | slow | | DP | O(n^2) | optimal |"
XSS = '[hover me](https://evil.com" onmouseover="alert(document.domain))'
errs = []


def run():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
        pg.goto("http://localhost:8000", wait_until="networkidle")

        # 1) glued table renders
        tcount = pg.evaluate(
            "(md)=>{const d=document.createElement('div');d.innerHTML=renderMarkdown(md);"
            "return {tables:d.querySelectorAll('table').length, rows:d.querySelectorAll('tbody tr').length};}",
            GLUED,
        )
        ok_table = tcount["tables"] == 1 and tcount["rows"] == 2
        print(f"{'✓' if ok_table else '✗'} glued table -> {tcount}")

        # 2) XSS link cannot inject handlers. The definitive check: after the
        # browser PARSES the rendered HTML, no element has an event-handler
        # attribute (the quote is escaped, so the payload stays inside href).
        xss = pg.evaluate(
            """(md)=>{
                const d=document.createElement('div'); d.innerHTML=renderMarkdown(md);
                const a=d.querySelector('a');
                return { handlerEls: d.querySelectorAll('[onmouseover],[onerror],[onload],[onclick]').length,
                         onmouseover: a?a.getAttribute('onmouseover'):'NO_ANCHOR' };
            }""",
            XSS,
        )
        ok_xss = xss["handlerEls"] == 0 and xss["onmouseover"] is None
        print(f"{'✓' if ok_xss else '✗'} XSS link neutralised -> handler attrs = {xss['handlerEls']}")

        # 3) live streaming run keeps its Mermaid diagram (the rAF-race fix)
        pg.click('.tab[data-mode="interview"]')
        pg.select_option("#model-select", "haiku")
        if "is-on" in (pg.get_attribute("#thinking-toggle", "class") or ""):
            pg.click("#thinking-toggle")
        pg.fill("#input", "Interview walkthrough for inverting a binary tree. You MUST include a ```mermaid flowchart of a small tree (root with two children). Keep it short.")
        pg.click("#send-btn")
        pg.wait_for_function("!document.getElementById('send-btn').disabled", timeout=180000)
        pg.wait_for_timeout(1500)  # let any stale frame fire (would wipe the SVG if unfixed)
        counts = pg.evaluate(
            """()=>{
                const panel=document.querySelector('.transcript[data-mode=\"interview\"]');
                return {
                    blocks: panel.querySelectorAll('.mermaid-block').length,
                    rendered: panel.querySelectorAll('.mermaid-block.rendered svg').length,
                    raw_left: panel.querySelectorAll('.mermaid-block:not(.rendered) .mermaid-src').length,
                };
            }"""
        )
        # diagram must be present AND rendered (not reverted to raw source)
        ok_mermaid = counts["blocks"] >= 1 and counts["rendered"] >= 1 and counts["raw_left"] == 0
        print(f"{'✓' if ok_mermaid else '✗'} live mermaid survived -> {counts}")
        pg.screenshot(path="screenshots/verify_mermaid.png", full_page=True)

        b.close()
        return ok_table and ok_xss and ok_mermaid


if __name__ == "__main__":
    ok = run()
    if errs:
        print("CONSOLE ERRORS:", errs[:8])
    print("\n" + ("✅ ALL FIXES VERIFIED" if ok and not errs else "❌ SOME CHECK FAILED"))
    sys.exit(0 if ok and not errs else 1)

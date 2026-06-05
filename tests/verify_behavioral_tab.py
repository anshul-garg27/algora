"""Verify the 5th (Behavioral) tab: it appears in the nav, switches, shows its empty state,
and a behavioral answer renders cleanly. Runs against the throwaway server on :8011."""

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
BASE = "http://127.0.0.1:8011"
SAMPLE = (ROOT / "screenshots" / "behavioral_sample.md").read_text(encoding="utf-8")

HARNESS = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="styles.css"></head>
<body><div class="app"><main class="messages"><div class="msg assistant">
<div class="bubble" id="out"></div></div></main></div>
<script src="markdown.js"></script>
<script>document.getElementById('out').innerHTML = renderMarkdown(%s);</script>
</body></html>"""


def main() -> int:
    harness = FRONTEND / "_behavioral_harness.html"
    harness.write_text(HARNESS % json.dumps(SAMPLE), encoding="utf-8")
    errors = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1100, "height": 950}, device_scale_factor=2)
            cerr = []
            pg.on("console", lambda m: cerr.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: cerr.append(f"pageerror: {e}"))

            # 1) the live app: 5 tabs, behavioral present, switch + empty state
            pg.goto(BASE, wait_until="networkidle")
            pg.wait_for_timeout(400)
            tabs = pg.locator(".tab").all_inner_texts()
            beh_tab = pg.locator('.tab[data-mode="behavioral"]')
            stats = {"tabCount": len(tabs), "tabs": [t.strip() for t in tabs],
                     "behavioralTabPresent": beh_tab.count() == 1}
            beh_tab.click()
            pg.wait_for_timeout(300)
            panel = pg.locator('.transcript[data-mode="behavioral"]')
            stats["behavioralActiveAfterClick"] = "is-active" in (panel.get_attribute("class") or "")
            stats["emptyStateText"] = pg.locator('.transcript[data-mode="behavioral"] .empty-state h2').inner_text()
            stats["exampleChips"] = pg.locator('.transcript[data-mode="behavioral"] .example-chip').count()
            pg.screenshot(path=str(ROOT / "screenshots" / "behavioral_tab.png"))

            # 2) render a real behavioral answer
            pg.goto(harness.as_uri(), wait_until="networkidle")
            pg.wait_for_timeout(400)
            stats["answerHeadings"] = pg.locator("#out h3").all_inner_texts()
            stats["sayItScriptPresent"] = "🎙️" in pg.locator("#out").inner_text()
            stats["answerConsoleErrors"] = cerr[:5]
            pg.locator("#out").screenshot(path=str(ROOT / "screenshots" / "behavioral_answer.png"))
            b.close()

        print(json.dumps(stats, indent=2, ensure_ascii=False))
        if stats["tabCount"] != 5: errors.append(f"expected 5 tabs, got {stats['tabCount']}")
        if not stats["behavioralTabPresent"]: errors.append("behavioral tab missing")
        if not stats["behavioralActiveAfterClick"]: errors.append("behavioral tab didn't activate")
        if stats["exampleChips"] < 1: errors.append("no example chips")
        if cerr: errors.append(f"console errors: {cerr}")
    finally:
        harness.unlink(missing_ok=True)

    if errors:
        print("FAIL:", *errors, sep="\n  - ")
        return 1
    print("PASS — behavioral tab renders, switches, and answers display.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

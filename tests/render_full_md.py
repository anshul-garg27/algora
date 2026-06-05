"""Render the real generated url_shortener_full.md through the frontend and capture the
diagrams (colored + readable) and the Bad/Good/Great tier cards, to confirm visual quality."""

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
MD = (ROOT / "screenshots" / "url_shortener_full.md").read_text(encoding="utf-8")

HARNESS = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="styles.css"></head>
<body><div class="app"><main class="messages"><div class="msg assistant">
<div class="bubble" id="out"></div></div></main></div>
<script src="markdown.js"></script>
<script>
  window.__MD__ = %s;
  document.getElementById('out').innerHTML = renderMarkdown(window.__MD__);
  window.__done__ = renderMermaidIn(document.getElementById('out'));
</script></body></html>"""


def main() -> int:
    harness = FRONTEND / "_full_md_harness.html"
    harness.write_text(HARNESS % json.dumps(MD), encoding="utf-8")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 900, "height": 1200}, device_scale_factor=2)
            errs = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            page.goto("http://localhost:8000/_full_md_harness.html", wait_until="networkidle")
            page.wait_for_timeout(2500)

            diagrams = page.locator(".mermaid-block.rendered")
            tiers = page.locator(".tier")
            stats = {
                "renderedDiagrams": diagrams.count(),
                "failedDiagrams": page.locator(".mermaid-block.mermaid-error").count(),
                "tierCards": tiers.count(),
                "tierBad": page.locator(".tier-bad").count(),
                "tierGood": page.locator(".tier-good").count(),
                "tierGreat": page.locator(".tier-great").count(),
                "tables": page.locator("table").count(),
                "consoleErrors": errs[:5],
            }
            # colored nodes in the first diagram
            if diagrams.count():
                fills = page.eval_on_selector_all(
                    ".mermaid-block svg .node rect, .mermaid-block svg .node polygon, .mermaid-block svg .node path",
                    "els => Array.from(new Set(els.map(e => getComputedStyle(e).fill))).filter(Boolean)",
                )
                stats["distinctNodeFillsAcrossDiagrams"] = len(fills)
                # screenshot the LAST diagram (usually 'Final high-level') and a deep-dive diagram
                diagrams.last.scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                diagrams.last.screenshot(path=str(ROOT / "screenshots" / "full_md_final_diagram.png"))
                # zoom it
                diagrams.last.click()
                page.wait_for_timeout(400)
                if page.locator(".mermaid-zoom").count():
                    page.screenshot(path=str(ROOT / "screenshots" / "full_md_diagram_zoom.png"), full_page=False)
                    page.keyboard.press("Escape")
            if tiers.count():
                tiers.first.scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                # screenshot the deep-dive region (first tier's parent area)
                page.screenshot(path=str(ROOT / "screenshots" / "full_md_tiers.png"), full_page=False)

            browser.close()
        print(json.dumps(stats, indent=2))
        ok = (stats["renderedDiagrams"] >= 1 and stats["failedDiagrams"] == 0
              and stats["tierCards"] >= 1 and not stats["consoleErrors"])
        print("PASS" if ok else "CHECK", "— diagrams + tiers rendered")
        return 0 if ok else 1
    finally:
        harness.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())

"""Render the Bad/Good/Great deep-dive markdown in a real browser and verify the
tier-card UI: three colored cards, badges, dd-labels, glued-header split, no stray
'#' paragraphs, and §Reliability staying OUTSIDE any tier card."""

import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

# Mimics the kind of design output the model streams: a glued header
# ("…numbers)### Key numbers"), a #### deep-dive question, and #### Bad/Good/Great.
SAMPLE = r"""## 3. Scale & Capacity (talkable numbers)### Key numbers

~750K writes/s is the binding number.

## 8. Deep Dives — Bad → Good → Great

### How do we survive 750K writes/s without melting the datastore?

#### Bad: Write every ping straight to a geo database

**Approach:** Each ping does `INSERT`/`GEOADD` into Postgres+PostGIS. **Challenges:** 750K writes/s × indexes needs dozens of shards; reads compete with writes. The DB becomes the bottleneck.

#### Good: Write raw pings to Kafka, query on read

**Approach:** Buffer in Kafka, compute heatmap at query time. **Challenges:** Read becomes a 65B-row scan — too slow for a 200ms SLO.

#### Great: Stream pre-aggregation (count-min / HLL in tumbling windows)

**Approach:** Flink folds pings into per-cell counters; Redis only sees aggregates. **Trade-off:** ~minute-stale heatmap, which is fine.

## 9. Reliability

This must NOT be inside a tier card.
"""

HARNESS = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="styles.css"></head>
<body><div class="app"><main class="messages"><div class="msg assistant">
<div class="bubble" id="out"></div></div></main></div>
<script src="markdown.js"></script>
<script>
  window.__SAMPLE__ = %r;
  document.getElementById('out').innerHTML = renderMarkdown(window.__SAMPLE__);
</script></body></html>"""


def main() -> int:
    harness = FRONTEND / "_tier_harness.html"
    harness.write_text(HARNESS % SAMPLE, encoding="utf-8")
    errors: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 760, "height": 1100})
            console_errs: list[str] = []
            page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
            page.goto(harness.as_uri())
            page.wait_for_timeout(250)

            tiers = page.locator(".tier")
            counts = {
                "tiers": tiers.count(),
                "bad": page.locator(".tier-bad").count(),
                "good": page.locator(".tier-good").count(),
                "great": page.locator(".tier-great").count(),
                "badges": page.locator(".tier-badge").all_inner_texts(),
                "ddLabels": page.locator(".dd-label").count(),
            }
            # glued header "…numbers)### Key numbers" must have split into its own h3
            counts["gluedHeaderSplit"] = page.locator("h3", has_text="Key numbers").count()
            # §9 Reliability must be an <h2>, NOT wrapped in a .tier card
            counts["reliabilityInsideTier"] = page.locator(".tier h2, .tier .tier-title", has_text="Reliability").count() > 0
            # stray "#" paragraphs (the bug we just fixed)
            body_text = page.locator("#out").inner_text()
            stray = [ln for ln in body_text.splitlines() if ln.strip() == "#"]
            counts["strayHashLines"] = len(stray)
            counts["consoleErrors"] = console_errs

            page.screenshot(path=str(ROOT / "screenshots" / "tiers_demo.png"), full_page=True)
            browser.close()

        print(counts)
        if counts["tiers"] != 3: errors.append("expected 3 tier cards")
        if not (counts["bad"] == counts["good"] == counts["great"] == 1):
            errors.append("expected exactly one of each tier color")
        if [b.lower() for b in counts["badges"]] != ["bad", "good", "great"]:
            errors.append("badges wrong/out of order")
        if counts["ddLabels"] < 5: errors.append("dd-labels missing")
        if counts["gluedHeaderSplit"] != 1: errors.append("glued header not split")
        if counts["reliabilityInsideTier"]: errors.append("Reliability leaked into a tier card")
        if counts["strayHashLines"] != 0: errors.append(f"stray '#' lines: {counts['strayHashLines']}")
        if counts["consoleErrors"]: errors.append(f"console errors: {counts['consoleErrors']}")
    finally:
        harness.unlink(missing_ok=True)

    if errors:
        print("FAIL:", *errors, sep="\n  - ")
        return 1
    print("PASS — tier-card UI renders clean (no stray '#', correct colors/labels).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

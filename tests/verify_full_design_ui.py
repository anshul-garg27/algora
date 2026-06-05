"""Render a FULL System-Design answer (every section the HLD prompt emits) so we can
eyeball every rendered surface at once and catch rough UI beyond the tier cards:
above/below-the-line requirements, capacity + API + trade-off tables, a growing
architecture diagram, Bad/Good/Great cards, and the interviewer-questions list."""

import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

SAMPLE = r"""# Design a Real-Time Ride-Sharing Heatmap

## 1. Requirements

### Functional (above the line)
- ✅ Drivers send a GPS ping every 4s.
- ✅ Riders see a live demand/supply heatmap for their city.
- ✅ Heatmap refreshes within ~5s of reality.

### Out of scope (below the line)
- ❌ Matching a rider to a driver.
- ❌ Pricing / surge computation.
- ❌ Trip lifecycle & payments.

## 2. Scale & Capacity (talkable numbers)
| Quantity | Estimate | How we got it |
|----------|----------|---------------|
| Active drivers | ~3M | peak, global |
| Ping rate | ~750K/s | 3M ÷ 4s |
| Heatmap reads | ~150K/s | riders opening the app |
| Hot state | ~30 GB | cells × counters in RAM |

## 3. API
| Endpoint | Request | Response |
|----------|---------|----------|
| `POST /v1/ping` | `{driverId, lat, lng, ts}` | `202 Accepted` |
| `GET /v1/heatmap` | `?city=...&zoom=...` | `{cells: [...]}` |

## 4. High-Level Design
```mermaid
flowchart LR
  D[Driver app] -->|ping| GW[Ingest gateway]
  GW --> K[(Kafka)]
  K --> F[Flink aggregator]
  F --> R[(Redis cells)]
  Rider[Rider app] -->|GET heatmap| API[Read API]
  API --> R
```

## 8. Deep Dives — Bad → Good → Great

### How do we survive 750K writes/s without melting the datastore?

#### Bad: Write every ping straight to a geo database
**Approach:** Each ping does `INSERT`/`GEOADD` into Postgres+PostGIS. **Challenges:** 750K writes/s × indexes needs dozens of shards; reads compete with writes — the DB is the bottleneck.

#### Good: Write raw pings to Kafka, query on read
**Approach:** Buffer in Kafka, compute the heatmap at query time. **Challenges:** Read becomes a 65B-row scan — far too slow for a 200ms SLO.

#### Great: Stream pre-aggregation (count-min / HLL in tumbling windows)
**Approach:** Flink folds pings into per-cell counters; Redis only ever sees aggregates. **Trade-off:** the heatmap is ~1 minute stale, which riders never notice.

## 9. Trade-off Ledger
| Decision | We chose | Gave up | Why it's fine |
|----------|----------|---------|---------------|
| Freshness | 1-min windows | real-time | riders can't perceive sub-minute drift |
| Store | Redis | durable DB | heatmap is reconstructable from Kafka |

## 10. Questions an interviewer will likely ask
1. What happens when a Flink node dies mid-window?
2. How do you handle a city-sized hotspot (skew)?
3. Why Kafka and not a queue like SQS?
4. How do you backfill after a Redis flush?
"""

HARNESS = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="styles.css"></head>
<body><div class="app"><main class="messages"><div class="msg assistant">
<div class="bubble" id="out"></div></div></main></div>
<script src="markdown.js"></script>
<script>
  document.getElementById('out').innerHTML = renderMarkdown(%r);
  if (window.renderMermaidIn) window.renderMermaidIn(document.getElementById('out'));
</script></body></html>"""


def main() -> int:
    # Serve the harness through the running server (NOT file://) so the lazy
    # mermaid loader's absolute "/vendor/mermaid.min.js" path resolves.
    harness = FRONTEND / "_full_design_harness.html"
    harness.write_text(HARNESS % SAMPLE, encoding="utf-8")
    errors: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 820, "height": 1400}, device_scale_factor=2)
            console_errs: list[str] = []
            page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: console_errs.append(f"pageerror: {e}"))
            page.goto("http://localhost:8000/_full_design_harness.html", wait_until="networkidle")
            page.wait_for_timeout(1200)  # let mermaid render

            stats = {
                "tables": page.locator("table").count(),
                "tierCards": page.locator(".tier").count(),
                "mermaidSvg": page.locator(".mermaid-block svg").count(),
                "ddLabels": page.locator(".dd-label").count(),
                "h1": page.locator("h1").count(),
                "ddLabelsInsideTier": page.locator(".tier .dd-label").count(),
            }
            body = page.locator("#out").inner_text()
            stats["strayHashLines"] = sum(1 for ln in body.splitlines() if ln.strip() == "#")
            stats["rawMermaidLeft"] = "flowchart LR" in body  # source should be gone once rendered
            stats["consoleErrors"] = console_errs

            page.screenshot(path=str(ROOT / "screenshots" / "full_design_ui.png"), full_page=True)
            browser.close()

        print(stats)
        if stats["tables"] != 3: errors.append(f"expected 3 tables, got {stats['tables']}")
        if stats["tierCards"] != 3: errors.append("expected 3 tier cards")
        if stats["mermaidSvg"] != 1: errors.append("architecture diagram did not render to SVG")
        if stats["rawMermaidLeft"]: errors.append("raw mermaid source still visible")
        if stats["ddLabelsInsideTier"] < 5: errors.append("dd-labels not scoped inside tier cards")
        if stats["strayHashLines"] != 0: errors.append(f"stray '#' lines: {stats['strayHashLines']}")
        if stats["consoleErrors"]: errors.append(f"console errors: {stats['consoleErrors']}")
    finally:
        harness.unlink(missing_ok=True)

    if errors:
        print("FAIL:", *errors, sep="\n  - ")
        return 1
    print("PASS — full design answer renders clean across every surface.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

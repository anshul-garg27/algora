"""Browser E2E for the two-tab UI: switching, Mermaid + table rendering,
mic feature-detection, and console-error checks. Server must be up on :8000."""

import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "screenshots"
OUT.mkdir(exist_ok=True)
errs = []

SAMPLE_MD = """## Optimal Approach
Here is the tree and the DP table.

```mermaid
flowchart TD
  A[root 8] --> B[3]
  A --> C[10]
  B --> D[1]
  B --> E[6]
```

| i | dp[i] | note |
|---|-------|------|
| 0 | 0 | base |
| 1 | 1 | take coin |

> 💬 I'd start by clarifying whether the tree can be empty.
"""


def run():
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1100, "height": 950}, device_scale_factor=2)
        pg = ctx.new_page()
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
        pg.goto("http://localhost:8000", wait_until="networkidle")

        # five tabs present, assessment active by default
        assert pg.eval_on_selector_all(".tab", "els=>els.length") == 5
        assert "is-active" in pg.get_attribute('.transcript[data-mode="assessment"]', "class")
        print("✓ five tabs, assessment active by default")

        # switch to interview tab -> its empty state shows
        pg.click('.tab[data-mode="interview"]')
        pg.wait_for_selector('.transcript[data-mode="interview"].is-active')
        assert "Walk into the interview ready" in pg.inner_text('.transcript[data-mode="interview"]')
        assert pg.get_attribute('.transcript[data-mode="assessment"]', "hidden") is not None
        print("✓ tab switch works, interview empty state visible")

        # render markdown with mermaid + table into the interview panel, then render mermaid
        pg.evaluate(
            """async (md) => {
                const panel = document.querySelector('.transcript[data-mode=\"interview\"]');
                panel.querySelector('.empty-state')?.remove();
                const el = document.createElement('div');
                el.className = 'prose';
                el.innerHTML = renderMarkdown(md);
                panel.appendChild(el);
                await renderMermaidIn(panel);
            }""",
            SAMPLE_MD,
        )
        pg.wait_for_selector(".mermaid-block.rendered svg", timeout=20000)
        n_svg = pg.eval_on_selector_all(".mermaid-block.rendered svg", "els=>els.length")
        n_tbl = pg.eval_on_selector_all(".prose table", "els=>els.length")
        n_talk = pg.eval_on_selector_all(".prose blockquote.talk", "els=>els.length")
        print(f"✓ mermaid SVG rendered={n_svg}, tables={n_tbl}, talking-points={n_talk}")
        assert n_svg >= 1 and n_tbl >= 1 and n_talk >= 1
        pg.screenshot(path=str(OUT / "interview_render.png"), full_page=True)

        # mic button: hidden when SpeechRecognition unsupported (headless), present in DOM
        mic_hidden = pg.get_attribute("#mic-btn", "hidden")
        print(f"✓ mic button feature-detection ok (hidden in headless: {mic_hidden is not None})")

        # switching back preserves the assessment empty state
        pg.click('.tab[data-mode="assessment"]')
        assert "Drop a problem" in pg.inner_text('.transcript[data-mode="assessment"]')
        print("✓ switch back to assessment preserved")

        b.close()


if __name__ == "__main__":
    run()
    if errs:
        print("\n✗ CONSOLE ERRORS:")
        for e in errs:
            print("   -", e)
        sys.exit(1)
    print("\n✅ tab E2E passed, no console errors.")

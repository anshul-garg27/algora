"""Real-browser E2E: load the UI, submit a problem, watch the agent render live.

Run with the server already up on :8000. Captures console errors and writes
screenshots at desktop and iPhone viewports.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
OUT = Path(__file__).resolve().parent.parent / "screenshots"
OUT.mkdir(exist_ok=True)

console_errors = []


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ---- iPhone 13-ish viewport ----
        iphone = browser.new_context(viewport={"width": 390, "height": 844},
                                     device_scale_factor=3, is_mobile=True)
        page = iphone.new_page()
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))
        page.goto(BASE, wait_until="networkidle")
        page.wait_for_selector(".transcript.is-active .empty-state")
        page.screenshot(path=str(OUT / "mobile_empty.png"))
        print("✓ mobile empty state rendered")

        # submit a problem and watch the live agent
        page.fill("#input", "Solve: reverse an integer without overflow. Test with 123 -> 321 and -120 -> -21. Write code, run it, verify, then answer.")
        # set haiku + thinking off for a fast deterministic run
        page.select_option("#model-select", "haiku")
        if "is-on" in (page.get_attribute("#thinking-toggle", "class") or ""):
            page.click("#thinking-toggle")
        page.click("#send-btn")

        # user bubble should appear immediately
        page.wait_for_selector(".msg.user", timeout=5000)
        print("✓ user message rendered")
        # assistant turn appears
        page.wait_for_selector(".msg.assistant", timeout=15000)
        # wait for at least one tool card (proves the agent ran a tool live)
        page.wait_for_selector(".tool-card", timeout=90000)
        print("✓ tool card rendered live")
        # wait until streaming finishes (send button re-enabled)
        page.wait_for_function("!document.getElementById('send-btn').disabled", timeout=120000)
        # final answer prose present
        page.wait_for_selector(".msg.assistant .prose", timeout=5000)
        print("✓ streaming completed, final answer present")

        n_tools = page.eval_on_selector_all(".tool-card", "els => els.length")
        n_code = page.eval_on_selector_all(".code-block", "els => els.length")
        print(f"  tool cards: {n_tools}, code blocks: {n_code}")
        page.screenshot(path=str(OUT / "mobile_solved.png"), full_page=True)
        iphone.close()

        # ---- desktop viewport ----
        desktop = browser.new_context(viewport={"width": 1440, "height": 900})
        dpage = desktop.new_page()
        dpage.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        dpage.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))
        dpage.goto(BASE, wait_until="networkidle")
        dpage.wait_for_selector(".transcript.is-active .empty-state")
        dpage.click('.transcript[data-mode="assessment"] .example-chip')  # populates the input
        assert dpage.input_value("#input"), "example chip should fill the input"
        dpage.screenshot(path=str(OUT / "desktop_empty.png"))
        print("✓ desktop renders, example chip works")
        desktop.close()

        browser.close()


if __name__ == "__main__":
    run()
    if console_errors:
        print("\n✗ CONSOLE ERRORS:")
        for e in console_errors:
            print("   -", e)
        sys.exit(1)
    print("\n✅ E2E passed with no console errors.")

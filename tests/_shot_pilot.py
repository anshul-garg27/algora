"""Load the REAL app for the pilot session, screenshot it, and verify the new
§3.5 API table, §4.1 per-class blocks, and the inline tabbed code viewer rendered."""

import sys
from playwright.sync_api import sync_playwright

SID = "5042a3ff-3829-402c-9802-6297bcbb1168:lld"
URL = f"https://localhost:8000/?s={SID}"
OUT = "/Users/gbang/Downloads/algora/screenshots"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1100, "height": 1500},
            device_scale_factor=2,
            ignore_https_errors=True,
        )
        page = ctx.new_page()
        errs = []
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(3500)  # let restore + mermaid + code viewer render

        def count(sel):
            return page.locator(sel).count()

        stats = {
            "prose_blocks": count(".prose"),
            "mermaid_rendered": count(".mermaid-block.rendered, .mermaid svg"),
            "inline_fullcode_section": count(".inline-fullcode"),
            "ifc_tabs": count(".ifc-tab"),
            "tool_cards": count(".tool-call, .tool"),
            "tables": count("table"),
        }

        # Does the §3.5 API contract table text show up anywhere in the rendered DOM?
        body_text = page.locator("body").inner_text()
        stats["has_3_5_heading"] = "API / System Interface" in body_text
        stats["has_contract_cols"] = ("Signature" in body_text and "Raises" in body_text)
        stats["has_complete_code_impl"] = "Complete Code Implementation" in body_text
        # tab names = the 6 files
        tab_names = page.locator(".ifc-tab-name").all_inner_texts()
        stats["ifc_tab_names"] = tab_names

        print("RENDER STATS:")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        if errs:
            print("CONSOLE ERRORS:", errs[:5])
        else:
            print("CONSOLE ERRORS: none")

        # Full-page screenshot
        page.screenshot(path=f"{OUT}/pilot_resource_pool_full.png", full_page=True)
        print(f"\nsaved {OUT}/pilot_resource_pool_full.png")

        # Tight shot of the inline code viewer if present
        if stats["inline_fullcode_section"]:
            page.locator(".inline-fullcode").first.scroll_into_view_if_needed()
            page.wait_for_timeout(400)
            page.locator(".inline-fullcode").first.screenshot(
                path=f"{OUT}/pilot_resource_pool_codeviewer.png"
            )
            print(f"saved {OUT}/pilot_resource_pool_codeviewer.png")

        browser.close()
        # success = the new sections + viewer all present
        ok = (
            stats["has_3_5_heading"]
            and stats["has_contract_cols"]
            and stats["has_complete_code_impl"]
            and stats["inline_fullcode_section"] >= 1
            and len(tab_names) == 6
        )
        print("\nVERDICT:", "PASS" if ok else "CHECK SCREENSHOTS")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

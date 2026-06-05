"""Browser verification of design-mode rendering:
A) all Mermaid diagram kinds used by LLD/HLD render to SVG;
B) a live LLD run renders its diagrams and the read-aloud button works.
Server up on :8000.
"""

import sys
from playwright.sync_api import sync_playwright

DIAGRAMS = {
    "classDiagram": "classDiagram\n  class ParkingLot {\n    +park(v) Ticket\n    +leave(t)\n  }\n  class Vehicle\n  ParkingLot --> Vehicle",
    "sequenceDiagram": "sequenceDiagram\n  Driver->>Gate: arrive\n  Gate->>Lot: requestSpot\n  Lot-->>Gate: spotId\n  Gate-->>Driver: ticket",
    "flowchart_arch": "flowchart LR\n  C[Client] --> LB[Load Balancer]\n  LB --> S[Service]\n  S --> Cache[(Redis)]\n  S --> DB[(Postgres)]",
    "erDiagram": "erDiagram\n  USER ||--o{ URL : owns\n  URL { string short_code string long_url }",
}
errs = []


def run():
    ok = True
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1200, "height": 1000}, device_scale_factor=2)
        pg = ctx.new_page()
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
        pg.goto("http://localhost:8000", wait_until="networkidle")

        # A) each diagram kind renders to SVG
        print("A) Mermaid diagram kinds:")
        for name, code in DIAGRAMS.items():
            md = "```mermaid\n" + code + "\n```"
            rendered = pg.evaluate(
                """async (md) => {
                    const host=document.querySelector('.transcript.is-active');
                    const el=document.createElement('div'); el.className='prose';
                    el.innerHTML=renderMarkdown(md); host.appendChild(el);
                    await renderMermaidIn(host);
                    const blk=el.querySelector('.mermaid-block');
                    return !!(blk && blk.querySelector('svg'));
                }""", md)
            print(f"  {'✓' if rendered else '✗'} {name} -> SVG")
            ok &= rendered

        # B) live LLD run renders diagrams + read-aloud works
        print("B) live LLD run (sonnet, thinking off):")
        pg.click('.tab[data-mode="lld"]')
        pg.select_option("#model-select", "sonnet")
        if "is-on" in (pg.get_attribute("#thinking-toggle", "class") or ""):
            pg.click("#thinking-toggle")
        pg.fill("#input", "Low level design for a parking lot. Include a class diagram (```mermaid classDiagram) and write+run a tiny Python demo. Keep it concise.")
        pg.click("#send-btn")
        pg.wait_for_function("!document.getElementById('send-btn').disabled", timeout=300000)
        pg.wait_for_timeout(1500)
        res = pg.evaluate(
            """()=>{
                const p=document.querySelector('.transcript[data-mode="lld"]');
                return {
                    svgs: p.querySelectorAll('.mermaid-block.rendered svg').length,
                    rawLeft: p.querySelectorAll('.mermaid-block:not(.rendered) .mermaid-src').length,
                    tools: p.querySelectorAll('.tool-card').length,
                    speakBtnVisible: !!p.querySelector('.speak-btn:not([hidden])'),
                };
            }""")
        print(f"  diagrams rendered={res['svgs']}, rawLeft={res['rawLeft']}, toolCards={res['tools']}, speakBtn={res['speakBtnVisible']}")
        ok &= res["svgs"] >= 1 and res["rawLeft"] == 0 and res["speakBtnVisible"]

        # read-aloud actually starts speaking
        if res["speakBtnVisible"]:
            spoke = pg.evaluate(
                """()=>{
                    const p=document.querySelector('.transcript[data-mode="lld"]');
                    const btn=p.querySelector('.speak-btn'); btn.click();
                    return new Promise(r=>setTimeout(()=>r(window.speechSynthesis.speaking || btn.classList.contains('speaking')), 600));
                }""")
            print(f"  {'✓' if spoke else '✗'} read-aloud started (speechSynthesis active)")
            pg.evaluate("window.speechSynthesis.cancel()")
        pg.screenshot(path="screenshots/lld_live.png", full_page=True)
        b.close()
    return ok


if __name__ == "__main__":
    ok = run()
    if errs:
        print("CONSOLE ERRORS:", errs[:8])
    print("\n" + ("✅ DESIGN UI VERIFIED" if ok and not errs else "❌ CHECK FAILED"))
    sys.exit(0 if ok and not errs else 1)

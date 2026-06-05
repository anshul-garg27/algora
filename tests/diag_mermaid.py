"""Render each generated mermaid block in isolation and print the real error message."""
import json, pathlib, re, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
md = (ROOT / "screenshots" / "url_shortener_full.md").read_text(encoding="utf-8")
blocks = re.findall(r"```mermaid\n(.*?)```", md, re.DOTALL)

HARNESS = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<script src="/vendor/mermaid.min.js"></script>
<script>
window.__blocks__ = %s;
window.__run__ = async () => {
  mermaid.initialize({ startOnLoad:false, theme:"base", securityLevel:"strict",
    themeVariables:{fontSize:"16px"}, flowchart:{useMaxWidth:false, htmlLabels:true} });
  const out = [];
  for (let i=0;i<window.__blocks__.length;i++){
    try { await mermaid.render("d"+i, window.__blocks__[i]); out.push({i, ok:true}); }
    catch(e){ out.push({i, ok:false, err:String(e && e.message || e).slice(0,300)}); }
  }
  return out;
};
</script></body></html>"""


def main():
    h = FRONTEND / "_diag_mermaid.html"
    h.write_text(HARNESS % json.dumps(blocks), encoding="utf-8")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.goto("http://localhost:8000/_diag_mermaid.html", wait_until="networkidle")
            res = pg.evaluate("window.__run__()")
            b.close()
        for r in res:
            print(f"block {r['i']}: {'OK' if r['ok'] else 'FAIL'} {r.get('err','')}")
    finally:
        h.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

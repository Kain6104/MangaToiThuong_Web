"""Browser QA for hero sharpness, single-layer compositing, and action-bar flow."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from browser_hero_qa import CDP, CHROME, ROOT, wait_until


PORT = 8767
DEBUG_PORT = 9229
HEROES = ("H286", "H001", "H007")


def inspect(cdp: CDP, code: str, mode: str) -> dict:
    return cdp.evaluate(
        f"""(() => {{
            const visual = document.querySelector('.hero-modal-visual');
            const stage = document.querySelector('.hero-visual-stage');
            const bar = document.getElementById('hero-visual-controls');
            const nameBlock = document.querySelector('.hero-name-block');
            const name = document.getElementById('hero-modal-name');
            const portrait = document.getElementById('hero-modal-portrait');
            const motion = document.getElementById('hero-modal-motion');
            const skill = bar.querySelector('[data-visual-action="skill1"]');
            const sr = stage.getBoundingClientRect();
            const br = bar.getBoundingClientRect();
            const nr = nameBlock.getBoundingClientRect();
            const ms = getComputedStyle(motion);
            const ps = getComputedStyle(portrait);
            const bs = getComputedStyle(bar);
            const activeLayers = [portrait, motion].filter(node => {{
                const style = getComputedStyle(node);
                return style.visibility !== 'hidden' && Number(style.opacity) > 0.01;
            }}).length;
            return {{
                code: {json.dumps(code)},
                mode: {json.dumps(mode)},
                viewport: [innerWidth, innerHeight],
                natural: [motion.naturalWidth, motion.naturalHeight],
                displayed: [Math.round(motion.getBoundingClientRect().width), Math.round(motion.getBoundingClientRect().height)],
                stage: [Math.round(sr.width), Math.round(sr.height)],
                upscaled: motion.getBoundingClientRect().width > motion.naturalWidth + 1 || motion.getBoundingClientRect().height > motion.naturalHeight + 1,
                activeLayers,
                portrait: {{opacity: ps.opacity, visibility: ps.visibility, filter: ps.filter}},
                motion: {{opacity: ms.opacity, visibility: ms.visibility, filter: ms.filter, blend: ms.mixBlendMode, objectFit: ms.objectFit, imageRendering: ms.imageRendering}},
                bar: {{position: bs.position, wrap: bs.flexWrap, overflowX: bs.overflowX, buttons: bar.children.length}},
                barOverlapsName: br.bottom > nr.top + 0.5,
                name: {{text: name.textContent, height: Math.round(name.getBoundingClientRect().height), blockHeight: Math.round(nr.height)}},
                skillStatus: skill?.title || '',
                animated: visual.classList.contains('is-animated'),
                errors: window.__heroQaErrors || []
            }};
        }})()"""
    )


def open_hero(cdp: CDP, code: str) -> None:
    cdp.evaluate(
        f"document.querySelector('[data-hero-id] img[src*=\"{code}.png\"]')?.closest('[data-hero-id]').click(); true"
    )
    wait_until(lambda: cdp.evaluate("document.getElementById('hero-detail-modal').classList.contains('is-open')"))
    wait_until(
        lambda: cdp.evaluate(
            f"document.getElementById('hero-modal-motion').naturalWidth > 0 && document.getElementById('hero-modal-motion').currentSrc.includes('{code}/visual/idle.webp') && document.querySelector('.hero-modal-visual').classList.contains('is-animated')"
        ),
        timeout=45,
    )


def screenshot(cdp: CDP, name: str) -> str:
    output = ROOT / "build" / "hero-visual-qa" / f"{name}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = cdp.call("Page.captureScreenshot", {"format": "png", "fromSurface": True})
    output.write_bytes(base64.b64decode(payload["data"]))
    return str(output)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    profile = Path(tempfile.mkdtemp(prefix="mtt-hero-visual-qa-"))
    server = subprocess.Popen(
        ["python", "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    chrome = subprocess.Popen(
        [
            str(CHROME),
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-allow-origins=*",
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={profile}",
            f"http://127.0.0.1:{PORT}/heroes.html",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    cdp = None
    try:
        def server_ready():
            try:
                return urlopen(f"http://127.0.0.1:{PORT}/heroes.html", timeout=2).status == 200
            except Exception:
                return False

        wait_until(server_ready)

        def browser_page():
            try:
                pages = json.load(urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json", timeout=1))
                return next((page for page in pages if page.get("type") == "page"), None)
            except Exception:
                return None

        page = wait_until(browser_page)
        cdp = CDP(page["webSocketDebuggerUrl"])
        cdp.call("Runtime.enable")
        cdp.call("Page.enable")
        cdp.call(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "window.__heroQaErrors=[];addEventListener('error',e=>window.__heroQaErrors.push(String(e.error||e.message)));addEventListener('unhandledrejection',e=>window.__heroQaErrors.push(String(e.reason)));"},
        )
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 2, "mobile": False})
        cdp.call("Page.reload", {"ignoreCache": True})
        wait_until(lambda: cdp.evaluate("document.querySelectorAll('[data-hero-id]').length === 56"), timeout=30)

        results = []
        for index, code in enumerate(HEROES):
            cdp.evaluate(f"document.documentElement.classList.toggle('dark', {str(index != 1).lower()}); true")
            open_hero(cdp, code)
            results.append(inspect(cdp, code, "desktop-dark" if index != 1 else "desktop-light"))
            if code == "H286":
                screenshot(cdp, "H286-desktop-dark")
            cdp.evaluate("document.querySelector('#hero-visual-controls [data-visual-action=\"attack\"]')?.click(); true")
            wait_until(lambda: cdp.evaluate("document.querySelector('#hero-visual-controls [data-visual-action=\"attack\"]')?.classList.contains('is-active') && document.getElementById('hero-modal-motion').currentSrc.includes('/visual/attack.webp') && document.querySelector('.hero-modal-visual').classList.contains('is-animated')"))
            if code == "H286":
                time.sleep(0.12)
                screenshot(cdp, "H286-attack-desktop-dark")
            cdp.evaluate("document.querySelector('#hero-visual-controls [data-visual-action=\"skill1\"]')?.click(); true")
            wait_until(lambda: cdp.evaluate("document.querySelector('#hero-visual-controls [data-visual-action=\"skill1\"]')?.classList.contains('is-active') && document.getElementById('hero-modal-motion').currentSrc.includes('/visual/skill1.webp') && document.querySelector('.hero-modal-visual').classList.contains('is-animated')"))
            if code == "H286":
                time.sleep(0.18)
                screenshot(cdp, "H286-skill1-desktop-dark")
            cdp.evaluate("document.querySelector('[data-hero-close]').click(); true")

        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 3, "mobile": True})
        for dark in (False, True):
            cdp.evaluate(f"document.documentElement.classList.toggle('dark', {str(dark).lower()}); true")
            open_hero(cdp, "H286")
            results.append(inspect(cdp, "H286", "mobile-dark" if dark else "mobile-light"))
            screenshot(cdp, "H286-mobile-dark" if dark else "H286-mobile-light")
            cdp.evaluate("document.querySelector('[data-hero-close]').click(); true")

        failures = []
        for item in results:
            if item["natural"] != [1080, 1080]: failures.append(f"{item['code']} {item['mode']}: not 1080x1080")
            if item["upscaled"]: failures.append(f"{item['code']} {item['mode']}: CSS upscale")
            if item["activeLayers"] != 1: failures.append(f"{item['code']} {item['mode']}: activeLayers={item['activeLayers']}")
            if item["motion"]["filter"] != "none": failures.append(f"{item['code']} {item['mode']}: image filter")
            if item["motion"]["blend"] != "normal": failures.append(f"{item['code']} {item['mode']}: blend mode")
            if item["barOverlapsName"]: failures.append(f"{item['code']} {item['mode']}: action/name overlap")
            if item["bar"]["position"] == "absolute" or item["bar"]["wrap"] != "nowrap": failures.append(f"{item['code']} {item['mode']}: action flow")
            if "PARTIAL_VFX" not in item["skillStatus"]: failures.append(f"{item['code']} {item['mode']}: missing partial label")
            if item["errors"]: failures.append(f"{item['code']} {item['mode']}: browser errors")

        output = {"status": "PASS" if not failures else "FAIL", "heroes": results, "failures": failures}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        if failures:
            raise SystemExit(1)
    finally:
        if cdp:
            cdp.close()
        chrome.terminate()
        server.terminate()
        try:
            chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    main()

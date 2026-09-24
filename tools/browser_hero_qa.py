"""Headless Chrome smoke test for the hero database/modal without extra packages."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.request import urlopen

import websocket


ROOT = Path(__file__).resolve().parents[1]
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PORT = 8765
DEBUG_PORT = 9227


class CDP:
    def __init__(self, url: str):
        self.socket = websocket.create_connection(url, timeout=10, origin="http://localhost")
        self.counter = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self.counter += 1
        request_id = self.counter
        self.socket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.socket.recv())
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})

    def evaluate(self, expression: str):
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
        )
        payload = result.get("result", {})
        if payload.get("subtype") == "error":
            raise RuntimeError(payload.get("description", "Browser evaluation failed"))
        return payload.get("value")

    def close(self) -> None:
        self.socket.close()


def wait_until(predicate, timeout: float = 20.0, interval: float = 0.2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    raise TimeoutError("Browser condition timed out")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if not CHROME.exists():
        raise SystemExit(f"Chrome not found: {CHROME}")

    profile = Path(tempfile.mkdtemp(prefix="mtt-hero-qa-"))
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
        wait_until(lambda: urlopen(f"http://127.0.0.1:{PORT}/heroes.html", timeout=1).status == 200)

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
        cdp.call("Page.reload", {"ignoreCache": True})
        time.sleep(0.5)
        wait_until(lambda: cdp.evaluate("document.readyState === 'complete'"))
        wait_until(lambda: cdp.evaluate("document.querySelectorAll('[data-hero-id]').length === 56"), timeout=30)

        initial = cdp.evaluate(
            """({
                cards: document.querySelectorAll('[data-hero-id]').length,
                brokenImages: [...document.images].filter(img => img.getAttribute('src') && img.complete && img.naturalWidth === 0).length,
                title: document.title,
                firstCodes: [...document.querySelectorAll('[data-hero-id] .hero-card-code')].slice(0,11).map(el => el.textContent.trim().split(' ')[0]),
                rarityFilters: [...document.querySelectorAll('#hero-rarity-filters [data-rarity]')].map(el => el.dataset.rarity)
            })"""
        )
        cdp.evaluate("document.querySelector('[data-hero-id] img[src*=\"H001.png\"]')?.closest('[data-hero-id]').click(); true")
        wait_until(lambda: cdp.evaluate("document.getElementById('hero-detail-modal').classList.contains('is-open')"))
        wait_until(lambda: cdp.evaluate("!document.getElementById('hero-visual-controls').hidden"), timeout=30)

        modal = cdp.evaluate(
            """({
                open: document.getElementById('hero-detail-modal').classList.contains('is-open'),
                controls: [...document.querySelectorAll('#hero-visual-controls button')].map(b => b.dataset.visualAction),
                motionLoaded: document.getElementById('hero-modal-motion').naturalWidth > 0,
                heroId: document.querySelector('[data-hero-id] img[src*=\"H001.png\"]')?.closest('[data-hero-id]')?.dataset.heroId || ''
            })"""
        )

        tabs = []
        for name in ("overview", "skills", "bonds", "obtain"):
            cdp.evaluate(f"document.querySelector('[data-hero-tab=\"{name}\"]').click(); true")
            time.sleep(0.3)
            tabs.append(
                cdp.evaluate(
                    f"""(() => {{
                        const tab = document.querySelector('[data-hero-tab=\"{name}\"]');
                        return {{name:'{name}', active:tab.classList.contains('is-active'), selected:tab.getAttribute('aria-selected'), panelLength:document.getElementById('hero-modal-panel').textContent.trim().length}};
                    }})()"""
                )
            )

        cdp.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True},
        )
        cdp.evaluate("document.documentElement.classList.remove('dark');document.querySelector('[data-hero-tab=\"overview\"]').click();true")
        time.sleep(0.3)
        light_mobile = cdp.evaluate(
            """(() => {
                const tab=document.querySelector('[data-hero-tab="overview"]');
                const shell=document.querySelector('.hero-modal-shell');
                const style=getComputedStyle(tab);
                const indicator=getComputedStyle(tab,'::after');
                return {viewport:innerWidth,shellWidth:shell.getBoundingClientRect().width,active:tab.classList.contains('is-active'),border:style.borderColor,color:style.color,indicatorHeight:indicator.height,indicatorOpacity:indicator.opacity};
            })()"""
        )
        cdp.evaluate("document.documentElement.classList.add('dark');true")
        time.sleep(0.3)
        dark_mobile = cdp.evaluate(
            """(() => {
                const tab=document.querySelector('[data-hero-tab="overview"]');
                const style=getComputedStyle(tab);
                return {active:tab.classList.contains('is-active'),border:style.borderColor,color:style.color};
            })()"""
        )

        cdp.evaluate("document.querySelector('#hero-visual-controls [data-visual-action=\"attack\"]')?.click(); true")
        time.sleep(0.1)
        attack_active = cdp.evaluate(
            "document.querySelector('#hero-visual-controls [data-visual-action=\"attack\"]')?.classList.contains('is-active') === true"
        )
        cdp.evaluate("document.querySelector('[data-hero-close]').click(); true")
        time.sleep(0.3)
        closed = cdp.evaluate("!document.getElementById('hero-detail-modal').classList.contains('is-open')")

        cdp.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False},
        )
        cdp.evaluate("document.querySelector('[data-hero-id] img[src*=\"H011.png\"]')?.closest('[data-hero-id]').click(); true")
        wait_until(lambda: cdp.evaluate("document.getElementById('hero-detail-modal').classList.contains('is-open')"))
        wait_until(lambda: cdp.evaluate("!document.getElementById('hero-visual-controls').hidden"), timeout=30)
        wait_until(lambda: cdp.evaluate("document.querySelector('.hero-modal-visual').classList.contains('is-animated')"), timeout=30)
        international_modal = cdp.evaluate(
            """(() => {
                const controls=document.getElementById('hero-visual-controls');
                const meta=document.querySelector('.hero-modal-visual-meta');
                const portrait=document.getElementById('hero-modal-portrait');
                const motion=document.getElementById('hero-modal-motion');
                const cr=controls.getBoundingClientRect(), mr=meta.getBoundingClientRect();
                return {
                    controls:[...controls.querySelectorAll('button')].map(b=>b.dataset.visualAction),
                    motionSize:[motion.naturalWidth,motion.naturalHeight],
                    staticVisibility:getComputedStyle(portrait).visibility,
                    staticOpacity:getComputedStyle(portrait).opacity,
                    motionVisibility:getComputedStyle(motion).visibility,
                    overlap:cr.bottom > mr.top + .5,
                    modalName:document.getElementById('hero-modal-name').textContent.trim()
                };
            })()"""
        )
        cdp.evaluate("document.querySelector('[data-hero-close]').click(); true")

        exceptions = cdp.evaluate("window.__heroQaErrors || []") or []
        result = {
            "status": "PASS" if initial["cards"] == 56 and initial["brokenImages"] == 0 and initial["firstCodes"] == ["H011","H013","H014","H152","H153","H293","H294","H431","H435","H436","H437"] and initial["rarityFilters"] == ["ALL","SR","SSS","SS","S","A","B"] and modal["open"] and modal["motionLoaded"] and {"idle", "attack", "skill1"}.issubset(modal["controls"]) and all(t["active"] and t["selected"] == "true" for t in tabs) and light_mobile["active"] and light_mobile["shellWidth"] <= light_mobile["viewport"] and light_mobile["indicatorHeight"] == "3px" and dark_mobile["active"] and attack_active and closed and international_modal["controls"] == ["idle","attack"] and international_modal["motionSize"] == [1080,1080] and international_modal["staticVisibility"] == "hidden" and international_modal["staticOpacity"] == "0" and international_modal["motionVisibility"] == "visible" and not international_modal["overlap"] and not exceptions else "FAIL",
            "initial": initial,
            "modal": modal,
            "tabs": tabs,
            "lightMobile": light_mobile,
            "darkMobile": dark_mobile,
            "attackActive": attack_active,
            "closed": closed,
            "internationalModal": international_modal,
            "exceptions": exceptions,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] != "PASS":
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

"""Isolated real-Chromium UI checks. No production data, camera, or remote API.

The fixture server uses real application routes and disposable storage. Chromium
gets a new profile. All browser requests outside loopback are blocked. This is
functional browser validation with synthetic sensor/AI/SMTP responses, not a
claim about field recognition quality. CDP is used directly (no dependency install).
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from urllib.request import Request, urlopen

import websocket

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = "http://127.0.0.1:8765"
DEBUG = "http://127.0.0.1:8766"


def http(path, body=None, method=None):
    url = path if path.startswith("http") else BASE + path
    request = Request(url, data=None if body is None else json.dumps(body).encode(),
                      method=method or ("POST" if body is not None else "GET"),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def ready(url, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return http(url)
        except Exception:
            time.sleep(.2)
    raise RuntimeError(f"Service did not start: {url}")


class Browser:
    def __init__(self, endpoint):
        self.socket = websocket.create_connection(endpoint, timeout=10, suppress_origin=True)
        self.sequence = 0
        self.errors = []
        self.requests = []
        self.blocked_external = []
        self.mobile = False
        for command in ("Page.enable", "Runtime.enable", "Network.enable"):
            self.call(command)
        self.call("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})

    def send(self, method, params):
        self.sequence += 1
        self.socket.send(json.dumps({"id": self.sequence, "method": method, "params": params}))
        return self.sequence

    def call(self, method, params=None):
        identifier = self.send(method, params or {})
        while True:
            message = json.loads(self.socket.recv())
            if message.get("id") == identifier:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})
            event = message.get("method")
            data = message.get("params", {})
            if event == "Fetch.requestPaused":
                url = data["request"]["url"]
                if url.startswith((BASE + "/", "data:", "about:")):
                    self.send("Fetch.continueRequest", {"requestId": data["requestId"]})
                else:
                    self.blocked_external.append(url)
                    self.send("Fetch.failRequest", {"requestId": data["requestId"], "errorReason": "BlockedByClient"})
            elif event == "Runtime.exceptionThrown":
                self.errors.append(data.get("exceptionDetails", {}))
            elif event == "Network.requestWillBeSent":
                request = data["request"]
                self.requests.append({"url": request["url"], "method": request["method"]})

    def js(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if result.get("exceptionDetails"):
            raise RuntimeError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def wait(self, expression, timeout=20):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.js(expression):
                return
            time.sleep(.15)
        raise AssertionError(f"Timed out waiting for: {expression}")

    def pause(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.js("true")
            time.sleep(.1)

    def click(self, selector):
        encoded = json.dumps(selector)
        location = self.js(f"""(() => {{ const node=[...document.querySelectorAll({encoded})].find(n=>n.getClientRects().length && !n.disabled); if(!node) throw Error('No visible enabled element: '+{encoded}); node.scrollIntoView({{block:'center',behavior:'instant'}}); const r=node.getBoundingClientRect(); return {{x:r.x+r.width/2,y:r.y+r.height/2}}; }})()""")
        if self.mobile:
            self.call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{**location, "id": 1}]})
            self.call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            return
        self.call("Input.dispatchMouseEvent", {"type": "mousePressed", **location, "button": "left", "clickCount": 1})
        self.call("Input.dispatchMouseEvent", {"type": "mouseReleased", **location, "button": "left", "clickCount": 1})

    def fill(self, selector, value):
        self.js(f"""(() => {{ const n=document.querySelector({json.dumps(selector)}); n.focus(); n.value={json.dumps(value)}; n.dispatchEvent(new Event('input',{{bubbles:true}})); n.dispatchEvent(new Event('change',{{bubbles:true}})); }})()""")

    def screen(self, name):
        self.pause(.25)
        data = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        path = OUT / f"browser-{name}.png"
        path.write_bytes(base64.b64decode(data["data"]))
        return str(path.relative_to(OUT))

    def body(self):
        return self.js("document.body.innerText")


def run():
    profile = OUT / f"browser-profile-{time.time_ns()}"
    profile.mkdir()
    fixture_log = (OUT / "browser-fixture.log").open("w", encoding="utf-8")
    browser_log = (OUT / "browser-chromium.log").open("w", encoding="utf-8")
    report = {"kind": "real Chromium / synthetic camera, VLM, SMTP / isolated SQLite",
              "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "checks": [], "screenshots": []}
    processes = []
    browser = None
    success = False

    def passed(label, data=None):
        report["checks"].append({"name": label, "passed": True, "details": data})
        print("PASS", label, flush=True)

    def shot(name):
        report["screenshots"].append(browser.screen(name))

    try:
        fixture = subprocess.Popen([sys.executable, str(OUT / "browser_fixture_server.py")], cwd=ROOT,
                                   stdout=fixture_log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(fixture)
        initial = ready(BASE + "/__test__/state")
        report["fixture_initial"] = initial
        chrome = subprocess.Popen([
            "C:/Program Files/Google/Chrome/Application/chrome.exe", "--headless=new",
            f"--user-data-dir={profile}", "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=8766",
            "--disable-background-networking", "--disable-component-update", "--disable-sync",
            "--disable-extensions", "--no-first-run", "--no-default-browser-check",
            "--disable-features=OptimizationHints,MediaRouter", "--metrics-recording-only",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--window-size=1440,1000", "about:blank",
        ], stdout=browser_log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(chrome)
        ready(DEBUG + "/json/version")
        target = next(tab for tab in http(DEBUG + "/json/list") if tab["type"] == "page")
        browser = Browser(target["webSocketDebuggerUrl"])
        browser.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        browser.call("Page.navigate", {"url": BASE + "/"})
        browser.wait("document.querySelector('[data-stat=active]')?.textContent !== '—' && document.querySelector('[data-camera-stream]')?.naturalWidth > 0")
        passed("Desktop dashboard renders live synthetic preview and database counts")
        shot("dashboard-desktop")

        browser.click('.nav-item[data-route="items"]')
        browser.wait("document.querySelectorAll('#inventory-table-body tr[data-item-id]').length === 48")
        total = http("/api/items")["total"]
        assert int(browser.js("document.querySelector('#inventory-count').textContent")) == total
        browser.click("#inventory-next")
        browser.wait("document.querySelector('#inventory-range').textContent.startsWith('49')")
        passed("Inventory pagination shows exact server count and reaches second page", {"total": total})
        browser.fill("#category-filter", "valuable")
        expected = http("/api/items?category=valuable")["total"]
        browser.wait(f"document.querySelector('#inventory-count').textContent === '{expected}' && document.querySelector('#inventory-range').textContent.startsWith('1')")
        passed("Changing a category resets pagination and filters the complete database")
        shot("inventory-desktop")
        browser.fill("#category-filter", "")

        observed = http("/__test__/observation", {"name": "브라우저 자동 분석 물품", "delay_seconds": 8})
        observed_id = observed.get("id") or observed["item"]["id"]
        browser.click('.nav-item[data-route="items"]')
        browser.wait(f"!!document.querySelector('#inventory-table-body [data-item-id=\"{observed_id}\"]')")
        browser.click(f'#inventory-table-body tr[data-item-id="{observed_id}"]')
        browser.wait("document.querySelector('#item-dialog-content').textContent.includes('AI 분석 중')")
        shot("pending-detail")
        browser.wait("document.querySelector('#item-dialog-title').textContent === '브라우저 자동 분석 물품'", 25)
        passed("A camera observation appears pending and its open detail updates after a delayed AI result")
        shot("classified-detail")
        browser.click('[data-close-dialog="item-dialog"]')

        draft = http("/__test__/observation", {"name": "충돌 검사 AI 결과", "delay_seconds": 8})
        draft_id = draft.get("id") or draft["item"]["id"]
        browser.click('.nav-item[data-route="items"]')
        browser.wait(f"!!document.querySelector('#inventory-table-body tr[data-item-id=\"{draft_id}\"]')")
        browser.click(f'#inventory-table-body tr[data-item-id="{draft_id}"]')
        browser.wait("!!document.querySelector('#item-edit-form [name=name]')")
        browser.fill('#item-edit-form [name="name"]', "보존되어야 할 편집 초안")
        browser.click("#item-dialog-title")
        browser.pause(11)
        assert browser.js("document.querySelector('#item-edit-form [name=name]').value") == "보존되어야 할 편집 초안"
        browser.click('#item-edit-form button[type="submit"]')
        browser.wait("document.querySelector('#item-detail-edit-message').textContent.includes('저장하지 않았습니다')")
        assert browser.js("document.querySelector('#item-edit-form [name=name]').value") == "보존되어야 할 편집 초안"
        passed("Late AI cannot overwrite a dirty form; revision conflict preserves the draft")
        shot("edit-conflict")
        browser.click("[data-reload-item]")
        browser.wait("document.querySelector('#item-dialog-title').textContent === '충돌 검사 AI 결과'")
        browser.fill('#item-edit-form [name="name"]', "브라우저 편집 확인")
        browser.click('#item-edit-form button[type="submit"]')
        browser.wait("document.querySelector('#item-dialog-title').textContent === '브라우저 편집 확인'")
        passed("Explicit reread then a normal edit saves through the real PATCH endpoint")

        past = browser.js("(() => {const d=new Date(Date.now()-86400000);return new Date(d-d.getTimezoneOffset()*60000).toISOString().slice(0,16)})()")
        browser.fill('#item-edit-form [name="expires_at"]', past)
        browser.click('#item-edit-form button[type="submit"]')
        browser.wait("document.querySelector('#item-dialog-content .status-badge.expired') !== null")
        http("/api/maintenance/check-expirations", {})
        assert http(f"/api/items/{draft_id}")["status"] == "due"
        passed("Expiry editing reaches due state and the real scheduler checks notification delivery")
        shot("expired-detail")
        browser.click('[data-item-action="dispose"]')
        browser.click("#confirm-accept")
        browser.wait("!!document.querySelector('#item-dialog-content .status-badge.disposed')")
        browser.click('[data-item-action="restore"]')
        browser.wait("!!document.querySelector('#item-dialog-content [data-item-action=extend]')")
        browser.click('[data-item-action="extend"]')
        browser.wait("!document.querySelector('#item-dialog-content .status-badge.expired')")
        browser.click('[data-item-action="recover"]')
        browser.click("#confirm-accept")
        browser.wait("!!document.querySelector('#item-dialog-content .status-badge.recovered')")
        browser.click('[data-item-action="restore"]')
        browser.wait("!!document.querySelector('#item-dialog-content [data-item-action=recover]')")
        passed("Dispose, restore, extend, recover and restore work through visible buttons")
        browser.click('[data-item-action="dismiss"]')
        browser.click("#confirm-accept")
        browser.wait("!!document.querySelector('#item-dialog-content .status-badge.dismissed')")
        assert browser.js("document.querySelector('#item-edit-form').hidden")
        browser.click('[data-item-action="restore"]')
        browser.wait("!!document.querySelector('#item-edit-form [data-confirm-review=true]')")
        browser.click('[data-confirm-review="true"]')
        browser.wait("!document.querySelector('#item-dialog-content .analysis-review')")
        passed("Dismissed evidence is read-only; restoration requires explicit confirmation")
        shot("edited-detail-desktop")
        browser.click('[data-close-dialog="item-dialog"]')

        browser.click('[data-route="camera"]')
        browser.wait("!document.querySelector('#view-camera').hidden && document.querySelector('[data-camera-stream-secondary]').naturalWidth > 0")
        browser.click("[data-open-settings]")
        browser.wait("document.querySelector('#save-settings').disabled === false")
        browser.click('[data-settings-tab="camera"]')
        browser.click('[name="privacy_mode"]')
        browser.click("#save-settings")
        browser.wait("[...document.querySelectorAll('[data-camera-stream],[data-camera-stream-secondary]')].every(n=>!n.getAttribute('src'))")
        passed("Privacy settings immediately stop visible MJPEG connections")
        browser.click("[data-open-settings]")
        browser.wait("document.querySelector('#save-settings').disabled === false")
        browser.click('[data-settings-tab="camera"]')
        browser.click('[name="privacy_mode"]')
        browser.click("#save-settings")
        browser.wait("!!document.querySelector('[data-camera-stream-secondary]').getAttribute('src')")
        browser.click('#view-camera [data-rebaseline]')
        browser.click("#confirm-accept")
        browser.wait("document.querySelector('#toast-region').textContent.includes('재설정을 요청')")
        passed("Privacy exit reconnects preview; rebaseline request is distinct from completion")
        shot("camera-desktop")

        browser.call("Network.emulateNetworkConditions", {"offline": True, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        browser.wait("document.querySelector('#connection-banner').hidden === false", 20)
        browser.call("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        browser.wait("document.querySelector('#connection-banner').hidden === true && !!document.querySelector('[data-camera-stream-secondary]').getAttribute('src')", 20)
        passed("Browser network interruption recovers server status and preview automatically")

        browser.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True, "screenWidth": 390, "screenHeight": 844})
        browser.call("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 1})
        browser.mobile = True
        browser.pause(.5)
        browser.click('.mobile-nav [data-route="items"]')
        browser.wait("document.querySelector('#inventory-mobile .mobile-item-card')?.getClientRects().length > 0")
        browser.js("window.scrollTo(0,0)")
        assert browser.js("document.documentElement.scrollWidth <= innerWidth")
        shot("inventory-mobile")
        browser.click("#inventory-mobile .mobile-item-card")
        browser.wait("document.querySelector('#item-dialog').open && !!document.querySelector('#item-edit-form')")
        bounds = browser.js("(()=>{const r=document.querySelector('#item-dialog').getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight}})()")
        assert bounds["left"] >= 0 and bounds["right"] <= bounds["width"] + 1
        assert bounds["top"] >= 0 and bounds["bottom"] <= bounds["height"] + 1
        shot("detail-mobile")
        passed("Mobile inventory and editable detail fit a 390px viewport", bounds)
        assert not browser.errors, browser.errors
        passed("No uncaught JavaScript exceptions during the full browser workflow")
        report["fixture_final"] = http("/__test__/state")
        success = True
    except Exception as error:
        report["failure"] = {"error": str(error), "traceback": traceback.format_exc()}
        if browser:
            try:
                report["screenshots"].append(browser.screen("failure"))
                report["visible_text_at_failure"] = browser.body()
            except Exception:
                pass
        print("FAIL", str(error), flush=True)
    finally:
        report["passed"] = success
        if browser:
            report["javascript_exceptions"] = browser.errors
            report["browser_requests"] = browser.requests
            report["blocked_external_requests"] = browser.blocked_external
            browser.socket.close()
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        fixture_log.close()
        browser_log.close()
        # This profile was created by this run, and its absolute destination is
        # verified before recursive cleanup. User profiles are never inspected.
        if profile.resolve().parent == OUT.resolve() and profile.name.startswith("browser-profile-"):
            try:
                shutil.rmtree(profile)
            except OSError:
                report["temporary_profile_cleanup_pending"] = str(profile)
        (OUT / "browser-ui-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(run())

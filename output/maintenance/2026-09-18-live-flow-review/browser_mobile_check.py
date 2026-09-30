"""Short real-touch/mobile follow-up to the desktop browser workflow."""
import json
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

from browser_ui_check import BASE, DEBUG, OUT, ROOT, Browser, http, ready

profile = OUT / f"browser-profile-mobile-{time.time_ns()}"
profile.mkdir()
processes = []
browser = None
report = {"kind": "390px Chromium touch emulation, isolated synthetic fixture", "checks": [], "screenshots": []}
log = (OUT / "browser-mobile-processes.log").open("w", encoding="utf-8")
try:
    for command in [
        [sys.executable, "-X", "utf8", str(OUT / "browser_fixture_server.py")],
        ["C:/Program Files/Google/Chrome/Application/chrome.exe", "--headless=new", f"--user-data-dir={profile}",
         "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=8766", "--disable-background-networking",
         "--disable-component-update", "--disable-sync", "--disable-extensions", "--no-first-run", "--no-default-browser-check",
         "--disable-features=OptimizationHints,MediaRouter", "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "about:blank"],
    ]:
        processes.append(subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW))
    ready(BASE + "/__test__/state")
    ready(DEBUG + "/json/version")
    target = next(tab for tab in http(DEBUG + "/json/list") if tab["type"] == "page")
    browser = Browser(target["webSocketDebuggerUrl"])
    browser.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True, "screenWidth": 390, "screenHeight": 844})
    browser.call("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 1})
    browser.mobile = True
    browser.call("Page.navigate", {"url": BASE + "/#items"})
    browser.wait("document.querySelector('#inventory-mobile .mobile-item-card')?.getClientRects().length > 0")
    browser.pause(.5)
    diagnostic = """(()=>({viewport:{innerWidth,innerHeight,clientWidth:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth,screenWidth:screen.width,width:visualViewport.width,height:visualViewport.height,scale:visualViewport.scale,offsetLeft:visualViewport.offsetLeft,offsetTop:visualViewport.offsetTop},overflow:[...document.querySelectorAll('body *')].map(n=>({n,r:n.getBoundingClientRect()})).filter(({n,r})=>n.getClientRects().length && (r.right>390 || r.left<0)).map(({n,r})=>({tag:n.tagName,id:n.id,classes:n.className,right:r.right,left:r.left,width:r.width,position:getComputedStyle(n).position,overflow:getComputedStyle(n).overflow})).slice(0,35)}))()"""
    report['inventory_diagnostics'] = browser.js(diagnostic)
    assert browser.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth && innerWidth === 390 && visualViewport.width === 390")
    report["screenshots"].append(browser.screen("inventory-mobile"))
    report["checks"].append({"name": "390px mobile inventory renders without horizontal document overflow", "passed": True})
    browser.click("#inventory-mobile .mobile-item-card")
    browser.wait("document.querySelector('#item-dialog').open && !!document.querySelector('#item-edit-form')")
    browser.pause(.4)
    report['detail_diagnostics'] = browser.js(diagnostic)
    bounds = browser.js("(()=>{const r=document.querySelector('#item-dialog').getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight}})()")
    assert bounds["width"] == 390 and bounds["height"] == 844
    assert bounds["left"] >= 0 and bounds["right"] <= 390
    assert bounds["top"] >= 0 and bounds["bottom"] <= 844
    report["screenshots"].append(browser.screen("detail-mobile"))
    report["checks"].append({"name": "Touch opens mobile item detail; dialog fits the viewport", "passed": True, "bounds": bounds})
    browser.fill('#item-edit-form [name="name"]', "모바일 수정 확인")
    report['focused_diagnostics'] = browser.js(diagnostic)
    browser.click('#item-edit-form button[type="submit"]')
    browser.wait("document.querySelector('#item-dialog-title').textContent === '모바일 수정 확인'")
    report["checks"].append({"name": "Mobile editing and touch-submit save through the real API", "passed": True})
    browser.click('[data-close-dialog="item-dialog"]')
    browser.click('.mobile-nav [data-route="dashboard"]')
    browser.wait("!document.querySelector('#view-dashboard').hidden")
    browser.js("window.scrollTo({top:0,behavior:'instant'})")
    report["screenshots"].append(browser.screen("dashboard-mobile"))
    browser.click('.mobile-nav [data-route="camera"]')
    browser.wait("!document.querySelector('#view-camera').hidden && !!document.querySelector('[data-camera-stream-secondary]').getAttribute('src')")
    report["checks"].append({"name": "Bottom navigation responds to touch and activates the matching camera stream", "passed": True})
    assert not browser.errors, browser.errors
    report["passed"] = True
    print("PASS mobile layout, touch detail/edit/save and bottom navigation; no JavaScript exceptions", flush=True)
except Exception as error:
    report["passed"] = False
    report["failure"] = {"error": str(error), "traceback": traceback.format_exc()}
    if browser:
        try:
            report["screenshots"].append(browser.screen("mobile-failure"))
            report["visible_text_at_failure"] = browser.body()
        except Exception:
            pass
    print("FAIL", str(error), flush=True)
finally:
    if browser:
        report["javascript_exceptions"] = browser.errors
        report["browser_requests"] = browser.requests
        browser.socket.close()
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
    log.close()
    if profile.resolve().parent == OUT.resolve() and profile.name.startswith("browser-profile-mobile-"):
        try:
            shutil.rmtree(profile)
        except OSError:
            report["temporary_profile_cleanup_pending"] = str(profile)
    (OUT / "browser-mobile-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
raise SystemExit(0 if report["passed"] else 1)

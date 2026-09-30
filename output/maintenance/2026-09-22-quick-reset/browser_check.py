"""Quick-reset browser checks using only an isolated synthetic app fixture."""
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PREVIOUS = ROOT / "output/maintenance/2026-09-18-live-flow-review"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, PREVIOUS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if "--fixture" in sys.argv:
    fixture = load("fixture", "browser_fixture_server.py")
    fixture.REVIEW_DIR = OUT
    app, state = fixture.build_fixture()
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, lifespan="off", access_log=False)
    raise SystemExit

ui = load("browser_tools", "browser_ui_check.py")
ui.OUT = OUT
processes = []
browser = None
report = {"kind": "Chromium with isolated SQLite and synthetic camera/AI/SMTP", "checks": []}


def passed(name):
    report["checks"].append(name)
    print("PASS", name, flush=True)


try:
    with (OUT / "browser-processes.log").open("w", encoding="utf-8") as log:
        processes.append(subprocess.Popen(
            [sys.executable, str(Path(__file__)), "--fixture"], cwd=ROOT,
            stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW))
        initial = ui.ready(ui.BASE + "/__test__/state")
        fixture_root = Path(initial["fixture_dir"]).resolve()
        assert fixture_root.is_relative_to(OUT)
        assert initial["item_count"] > 0
        report["fixture_dir"] = str(fixture_root)
        settings_before = ui.http("/api/settings")
        processes.append(subprocess.Popen([
            "C:/Program Files/Google/Chrome/Application/chrome.exe", "--headless=new",
            f"--user-data-dir={OUT / ('browser-profile-' + str(time.time_ns()))}",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=8766",
            "--disable-background-networking", "--disable-component-update", "--disable-sync",
            "--disable-extensions", "--no-first-run", "--no-default-browser-check",
            "--disable-features=OptimizationHints,MediaRouter", "--metrics-recording-only",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "about:blank",
        ], stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW))
        ui.ready(ui.DEBUG + "/json/version")
        target = next(t for t in ui.http(ui.DEBUG + "/json/list") if t["type"] == "page")
        browser = ui.Browser(target["webSocketDebuggerUrl"])
        browser.call("Page.navigate", {"url": ui.BASE + "/"})
        browser.wait("Number(document.querySelector('[data-stat=active]')?.textContent)>0")
        for width in [1440, 1024, 390, 320]:
            browser.call("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": 1000 if width > 720 else 844,
                "deviceScaleFactor": 1, "mobile": width <= 720})
            browser.pause(.3)
            layout = browser.js("({viewport:innerWidth,width:document.documentElement.scrollWidth,button:document.querySelector('#quick-reset').getBoundingClientRect().toJSON()})")
            assert layout["width"] <= width, layout
            assert 0 <= layout["button"]["x"] and layout["button"]["right"] <= width, layout
            browser.screen(f"dashboard-{width}")
            browser.click("#quick-reset")
            browser.wait("document.querySelector('#reset-dialog').open")
            assert browser.js("document.querySelector('#reset-confirm-field').hidden")
            assert not browser.js("document.querySelector('#reset-submit').disabled")
            assert browser.js("document.activeElement.id") == "reset-cancel"
            browser.screen(f"confirmation-{width}")
            browser.click("#reset-cancel")
            browser.wait("!document.querySelector('#reset-dialog').open")
            assert ui.http("/__test__/state")["item_count"] == initial["item_count"]
            passed(f"{width}px layout and cancel preserve data")
        browser.click("#quick-reset")
        browser.click("#reset-submit")
        browser.wait("!document.querySelector('#reset-dialog').open && document.querySelector('[data-stat=active]').textContent==='0'")
        current = ui.http("/__test__/state")
        assert current["item_count"] == 0
        assert not list(Path(current["capture_dir"]).iterdir())
        assert not (fixture_root / "data/reset-backups").exists()
        assert ui.http("/api/settings") == settings_before
        assert len([r for r in browser.requests if r["method"] == "POST" and r["url"].endswith("/api/maintenance/reset")]) == 1
        browser.screen("reset-complete")
        passed("Confirmed quick reset deletes all fixture data without backup and preserves settings")
        browser.click('[data-open-demo]')
        browser.click('[data-demo-preset="phone"]')
        browser.wait("Number(document.querySelector('[data-stat=active]').textContent)===1")
        fresh = ui.http("/api/items")["items"][0]
        assert fresh["id"] > max(initial["seed_ids"]["all"])
        passed("Next simulated registration succeeds with a new item ID")
        browser.js("document.querySelector('#demo-dialog').close()")
        browser.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        browser.click('[data-open-settings]')
        browser.click('[data-settings-tab="system"]')
        browser.click('[data-reset-open]')
        browser.click('#confirm-accept')
        browser.wait("document.querySelector('#reset-dialog').open")
        assert not browser.js("document.querySelector('#reset-confirm-field').hidden")
        assert browser.js("document.querySelector('#reset-submit').disabled")
        assert browser.js("document.querySelector('#reset-submit').textContent") == "백업 후 초기화"
        browser.click('#reset-cancel')
        passed("Settings reset still requires typed confirmation and defaults to backup")
        assert not browser.errors, browser.errors
        report["status"] = "passed"
except Exception as exc:
    report["status"] = "failed"
    report["error"] = repr(exc)
    if browser:
        browser.screen("failure")
    raise
finally:
    (OUT / "browser-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if browser:
        browser.socket.close()
    for process in reversed(processes):
        process.terminate()
        process.wait(timeout=15)

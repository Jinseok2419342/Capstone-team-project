"use strict";

// Run with: node --test tests/frontend/app.test.cjs
// Exercise the production controller with deferred HTTP responses and a tiny DOM.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const vm = require("node:vm");

class Element {
  constructor(options = {}) {
    this.dataset = {};
    this.attributes = new Map();
    this.children = [];
    this.innerHTML = "";
    this.textContent = "";
    this.value = "";
    this.disabled = false;
    this.hidden = false;
    this.open = false;
    this.isConnected = true;
    this.classes = new Set();
    this.events = new Map();
    this.classList = {
      add: (...names) => names.forEach((name) => this.classes.add(name)),
      remove: (...names) => names.forEach((name) => this.classes.delete(name)),
      contains: (name) => this.classes.has(name),
      toggle: (name, on) => on ? this.classes.add(name) : this.classes.delete(name),
    };
    Object.assign(this, options);
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  hasAttribute(name) { return this.attributes.has(name); }
  removeAttribute(name) { this.attributes.delete(name); }
  toggleAttribute(name, on) { if (on) this.setAttribute(name, ""); else this.removeAttribute(name); }
  querySelector(selector) { return this.nodes?.[selector] || null; }
  querySelectorAll() { return []; }
  closest() { return null; }
  addEventListener(type, handler, options = {}) {
    const listeners = this.events.get(type) || [];
    listeners.push({ handler, once: options.once === true });
    this.events.set(type, listeners);
  }
  dispatch(type) {
    const listeners = this.events.get(type) || [];
    this.events.set(type, listeners.filter((listener) => !listener.once));
    for (const listener of listeners) listener.handler({ type, target: this });
  }
  appendChild(child) { this.children.push(child); }
  focus() { this.focused = true; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  set src(value) { this.setAttribute("src", value); }
  get src() { return this.getAttribute("src"); }
}

function setup() {
  const nodes = new Map();
  const groups = new Map();
  const requests = [];
  const document = {
    hidden: false,
    querySelector: (selector) => nodes.get(selector) || null,
    querySelectorAll: (selector) => groups.get(selector) || [],
    getElementById: (id) => nodes.get(`#${id}`) || null,
    createElement: () => new Element(),
    addEventListener() {},
  };
  const sandbox = {
    document, HTMLDialogElement: Element, HTMLImageElement: Element,
    URL, URLSearchParams, AbortController,
    navigator: { onLine: true },
    location: { origin: "http://localhost", hash: "" },
    history: { pushState() {} },
    window: { matchMedia: () => ({ matches: true }), setTimeout: () => 1, clearTimeout() {}, setInterval: () => 1, clearInterval() {}, scrollTo() {}, confirm: () => true, addEventListener() {} },
    FormData: class {
      constructor(form) { this.form = form; }
      get(name) { const input = this.form.elements.namedItem(name); return input && !input.disabled ? input.value : null; }
    },
    fetch(path, options) {
      return new Promise((resolve, reject) => {
        requests.push({ path, options, reject, reply: (data, status = 200) => resolve({ ok: status < 400, status, headers: { get: () => "application/json" }, json: async () => data }) });
      });
    },
  };
  const source = readFileSync(join(__dirname, "../../static/app.js"), "utf8");
  const exports = "state, loadDashboard, updateDashboard, loadItems, renderInventory, openItem, refreshOpenItem, renderItemDetail, loadSettings, settingsPayload, populateSettings, handleProviderChange, handleDocumentClick, handleItemAction, saveItemEdit, syncCameraStreams, setStreamHealth, handleImageError, retryFailedItemImages, refreshItemTiming, updateProvider, validateSettingsForm, effectiveStatus, reviewStatus, analysisBadgeMarkup, updateCameraMetrics, updateCamera, runDemoPreset, runDemoRecovery, beginQuickResetFlow, beginResetFlow, resetOperationalData";
  vm.createContext(sandbox);
  vm.runInContext(source.replace(/\}\)\(\);\s*$/, `globalThis.app = { ${exports} }; })();`), sandbox);
  return { ...sandbox.app, document, nodes, groups, requests, add(selector, options) { const node = new Element(options); nodes.set(selector, node); return node; } };
}

const flush = () => new Promise((resolve) => setImmediate(resolve));
const item = (id, name = `물품 ${id}`) => ({ id, name, provider: "manual", category: "general", status: "stored", expires_at: "2099-01-01T12:34:56+00:00" });

function resetDialog(app) {
  for (const id of ["reset-dialog", "reset-confirmation", "reset-submit", "reset-status", "reset-cancel", "reset-description", "quick-reset-description", "reset-confirm-field", "reset-dialog-title", "quick-reset", "toast-region"]) app.add(`#${id}`);
}

test("dashboard quick reset opens one confirmation and sends nothing until submitted", async () => {
  const app = setup();
  resetDialog(app);
  await app.handleDocumentClick({ target: { closest: (selector) => selector === "[data-quick-reset-open]" ? {} : null } });
  assert.equal(app.nodes.get("#reset-dialog").open, true);
  assert.equal(app.nodes.get("#reset-submit").disabled, false);
  assert.equal(app.nodes.get("#reset-submit").textContent, "백업 없이 초기화");
  assert.equal(app.nodes.get("#reset-confirm-field").hidden, true);
  assert.equal(app.nodes.get("#quick-reset-description").hidden, false);
  assert.equal(app.nodes.get("#reset-cancel").focused, true);
  assert.equal(app.requests.length, 0);
  app.nodes.get("#reset-dialog").close();
  assert.equal(app.requests.length, 0);
});

test("quick reset blocks duplicate submissions and refreshes the cleared dashboard", async () => {
  const app = setup();
  resetDialog(app);
  app.state.items = [item(1)];
  app.state.itemsTotal = 50;
  app.state.itemsOffset = 48;
  app.beginQuickResetFlow();
  const pending = app.resetOperationalData();
  assert.equal(app.state.resetInProgress, true);
  assert.equal(app.nodes.get("#quick-reset").disabled, true);
  assert.equal(app.nodes.get("#reset-cancel").disabled, true);
  await app.resetOperationalData();
  app.beginQuickResetFlow();
  assert.equal(app.requests.length, 1);
  assert.equal(app.requests[0].path, "/api/maintenance/reset");
  assert.deepEqual(JSON.parse(app.requests[0].options.body), { mode: "quick", confirmation: "시연 초기화" });
  app.requests[0].reply({ ok: true, backup_directory: null });
  await flush();
  assert.equal(app.nodes.get("#reset-dialog").open, false);
  assert.equal(app.state.items.length, 0);
  assert.equal(app.state.itemsOffset, 0);
  for (const request of app.requests.slice(1)) request.reply({});
  await pending;
  assert.equal(app.state.resetInProgress, false);
  assert.equal(app.nodes.get("#quick-reset").disabled, false);
  assert.match(app.nodes.get("#toast-region").children[0].innerHTML, /시연 데이터를 초기화/);
  assert.doesNotMatch(app.nodes.get("#toast-region").children[0].innerHTML, /백업 위치|백업도 함께/);
});

test("a failed quick reset preserves the current list and permits an explicit retry", async () => {
  for (const status of [409, 500]) {
    const app = setup();
    resetDialog(app);
    app.state.items = [item(1)];
    app.beginQuickResetFlow();
    const pending = app.resetOperationalData();
    app.requests[0].reply({ detail: "초기화 실패 테스트" }, status);
    await pending;
    assert.equal(app.nodes.get("#reset-dialog").open, true);
    assert.equal(app.state.items.length, 1);
    assert.equal(app.state.resetInProgress, false);
    assert.equal(app.nodes.get("#reset-submit").disabled, false);
    assert.equal(app.nodes.get("#reset-cancel").disabled, false);
    assert.equal(app.requests.length, 1);
    assert.equal(app.nodes.get("#reset-status").textContent, "초기화 실패 테스트");
  }
});

test("opening the settings reset after quick reset restores typing and the backup default", async () => {
  const app = setup();
  resetDialog(app);
  app.beginQuickResetFlow();
  app.nodes.get("#reset-dialog").close();
  await app.beginResetFlow();
  assert.equal(app.state.resetMode, "backup");
  assert.equal(app.nodes.get("#reset-confirm-field").hidden, false);
  assert.equal(app.nodes.get("#quick-reset-description").hidden, true);
  assert.equal(app.nodes.get("#reset-submit").disabled, true);
  await app.resetOperationalData();
  assert.equal(app.requests.length, 0);
  app.nodes.get("#reset-confirmation").value = "초기화";
  const pending = app.resetOperationalData();
  assert.deepEqual(JSON.parse(app.requests[0].options.body), { confirmation: "초기화" });
  app.requests[0].reply({ ok: true, backup_directory: "reset-backups/example" });
  await flush();
  for (const request of app.requests.slice(1)) request.reply({});
  await pending;
  assert.match(app.nodes.get("#toast-region").children[0].innerHTML, /백업 위치/);
});

test("recover, dispose, restore and dismiss report success after the server commits", async () => {
  for (const action of ["recover", "dispose", "restore", "dismiss"]) {
    const app = setup();
    const toasts = app.add("#toast-region");
    const button = new Element({ dataset: { id: "1", itemAction: action } });
    const pending = app.handleItemAction(button);
    await flush();
    assert.equal(app.requests[0].path, `/api/items/1/${action}`);
    app.requests[0].reply(item(1));
    await flush();
    assert.equal(app.requests[1].path, "/api/dashboard");
    app.requests[1].reply({});
    await pending;
    assert.equal(toasts.children.length, 1);
    assert.equal(toasts.children[0].className, "toast success");
    assert.equal(button.disabled, false);
  }
});

test("a newer search survives an older response and an older error", async () => {
  for (const failOlder of [false, true]) {
    const app = setup();
    const search = app.add("#item-search", { value: "first" });
    const first = app.loadItems({ silent: true });
    search.value = "second";
    const second = app.loadItems({ silent: true });
    assert.equal(app.requests.length, 2);
    app.requests[1].reply({ items: [item(2)] });
    await second;
    if (failOlder) app.requests[0].reject(new Error("connection lost"));
    else app.requests[0].reply({ items: [item(1)] });
    await first;
    assert.equal(app.state.items[0].id, 2);
    assert.equal(app.state.itemsLoading, false);
  }
});

test("a refresh after mutation supersedes an in-flight identical query", async () => {
  const app = setup();
  const first = app.loadItems({ silent: true });
  const refresh = app.loadItems({ silent: true, force: true });
  app.requests[1].reply({ items: [item(3)] });
  await refresh;
  app.requests[0].reply({ items: [] });
  await first;
  assert.equal(app.state.items[0].id, 3);
});

test("older dashboard failure cannot take a newer successful connection offline", async () => {
  const app = setup();
  const first = app.loadDashboard();
  const refresh = app.loadDashboard({ force: true });
  app.requests[1].reply({ stats: { active: 3 } });
  await refresh;
  app.requests[0].reject(new Error("stale failure"));
  await first;
  assert.equal(app.state.dashboard.stats.active, 3);
  assert.equal(app.state.serverOnline, true);
});

test("opening a second item cannot be overwritten by the first item's response", async () => {
  const app = setup();
  app.add("#item-dialog");
  const title = app.add("#item-dialog-title");
  app.add("#item-dialog-content");
  const first = app.openItem(1);
  const second = app.openItem(2);
  app.requests[1].reply(item(2, "두 번째 물품"));
  await second;
  app.requests[0].reply(item(1, "첫 번째 물품"));
  await first;
  assert.equal(title.textContent, "두 번째 물품");
});

function settingsForm(app) {
  const values = {
    ai_provider: "auto", ai_model: "model-a", ai_min_confidence: "0.15", camera_index: "0",
    camera_mains_frequency_hz: "0", preview_max_width: "1280",
    motion_delay_seconds: "20.25", motion_threshold: "3.75", privacy_mode: "",
    admin_email: "", smtp_host: "smtp.local", smtp_port: "587", smtp_username: "",
    valuable_value_threshold_krw: "100000",
  };
  const elements = Object.entries(values).map(([name, value]) => new Element({ name, value }));
  elements.namedItem = (name) => elements.find((element) => element.name === name) || null;
  app.add("#settings-form", { elements });
  app.nodes.set("#ai-provider", elements.namedItem("ai_provider"));
  app.nodes.set("#ai-model", elements.namedItem("ai_model"));
  return elements;
}

const settings = {
  provider: "auto", openai_model: "model-a", gemini_model: "model-b", ai_min_confidence: 0.15,
  camera_index: 0, settle_seconds: 20.25, motion_threshold: 3.75, privacy_mode: false,
  camera_mains_frequency_hz: 0, preview_max_width: 1280,
  admin_email: "", smtp_host: "smtp.local", smtp_port: 587, smtp_username: "", valuable_value_threshold_krw: 100000,
};

test("opening settings during startup awaits the shared request and populates safe values", async () => {
  const app = setup();
  const fields = settingsForm(app);
  const button = app.add("#save-settings");
  const content = app.add("#settings-content");
  const startup = app.loadSettings({ populate: false, silent: true });
  const opened = app.loadSettings({ populate: true });
  assert.equal(app.requests.length, 1);
  assert.equal(button.disabled, true);
  assert.equal(content.inert, true);
  app.requests[0].reply({ settings, provider: { active: "openai" } });
  await Promise.all([startup, opened]);
  assert.equal(fields.namedItem("motion_threshold").value, "3.75");
  assert.equal(fields.namedItem("motion_delay_seconds").value, "20.25");
  assert.equal(fields.namedItem("ai_min_confidence").value, "0.15");
  assert.equal(button.disabled, false);
  assert.equal(content.inert, false);
  assert.equal(Object.keys(app.settingsPayload()).length, 0);
  fields.namedItem("admin_email").value = "test@example.invalid";
  assert.deepEqual(JSON.parse(JSON.stringify(app.settingsPayload())), { admin_email: "test@example.invalid" });
});

test("model edits survive switching providers and automatic selection", () => {
  const app = setup();
  const fields = settingsForm(app);
  app.state.settings = settings;
  app.state.provider = { active: "openai" };
  app.populateSettings(settings, app.state.provider);
  fields.namedItem("ai_model").value = "edited-a";
  fields.namedItem("ai_provider").value = "gemini";
  app.handleProviderChange();
  assert.equal(fields.namedItem("ai_model").value, "model-b");
  fields.namedItem("ai_model").value = "edited-b";
  fields.namedItem("ai_provider").value = "auto";
  app.handleProviderChange();
  assert.equal(fields.namedItem("ai_model").value, "edited-a");
  assert.deepEqual(JSON.parse(JSON.stringify(app.settingsPayload())), { openai_model: "edited-a", gemini_model: "edited-b" });
});

test("hidden streams disconnect; returning to the view opens only its stream", () => {
  const app = setup();
  const dashboard = { hidden: false };
  const camera = { hidden: true };
  const main = new Element({ dataset: { streamSrc: "/camera/stream" }, closest: () => dashboard });
  const secondary = new Element({ dataset: { streamSrc: "/camera/stream" }, closest: () => camera });
  secondary.setAttribute("data-camera-stream-secondary", "");
  app.groups.set('[data-camera-stream], [data-camera-stream-secondary]', [main, secondary]);
  app.syncCameraStreams();
  assert.ok(main.src);
  assert.equal(secondary.src, null);
  dashboard.hidden = true;
  camera.hidden = false;
  app.syncCameraStreams();
  assert.equal(main.src, null);
  assert.ok(secondary.src);
  app.document.hidden = true;
  app.syncCameraStreams();
  assert.equal(secondary.src, null);
  app.document.hidden = false;
  app.state.dashboard = { camera: { privacy_enabled: true } };
  app.syncCameraStreams();
  assert.equal(secondary.src, null);
  assert.equal(secondary.hidden, true);
});

test("saving only the name preserves the full-precision expiry timestamp", async () => {
  const app = setup();
  const fields = [
    new Element({ name: "name", value: "수정한 물품" }), new Element({ name: "description", value: "" }),
    new Element({ name: "category", value: "general" }), new Element({ name: "expires_at", value: "2099-01-01T12:34" }),
  ];
  fields.namedItem = (name) => fields.find((field) => field.name === name);
  const form = new Element({ elements: fields, dataset: { id: "1", originalCategory: "general", originalExpiry: "2099-01-01T12:34" } });
  const pending = app.saveItemEdit(form);
  const body = JSON.parse(app.requests[0].options.body);
  assert.equal(body.name, "수정한 물품");
  assert.equal("expires_at" in body, false);
  app.requests[0].reply(item(1));
  await flush();
  app.requests[1].reply({});
  await pending;
});

test("upcoming expiry follows the configured alert period, including zero days", () => {
  const app = setup();
  const stored = { status: "stored", expires_at: new Date(Date.now() + 3 * 86400000).toISOString() };
  assert.equal(app.effectiveStatus(stored), "due_soon");
  app.state.settings = { alert_lead_days: 1 };
  assert.equal(app.effectiveStatus(stored), "active");
  app.state.settings.alert_lead_days = 5;
  assert.equal(app.effectiveStatus(stored), "due_soon");
  app.state.settings.alert_lead_days = 0;
  assert.equal(app.effectiveStatus(stored), "active");
});

test("camera tuning preserves the server profile and sends only changed numeric settings", () => {
  const app = setup();
  const fields = settingsForm(app);
  app.state.settings = { ...settings, preview_max_width: 800 };
  app.populateSettings(app.state.settings, { active: "openai" });
  assert.equal(fields.namedItem("preview_max_width").value, "800");
  assert.equal(fields.namedItem("camera_mains_frequency_hz").value, "0");
  assert.equal(Object.keys(app.settingsPayload()).length, 0);
  fields.namedItem("camera_mains_frequency_hz").value = "60";
  fields.namedItem("preview_max_width").value = "1001";
  assert.deepEqual(JSON.parse(JSON.stringify(app.settingsPayload())), { camera_mains_frequency_hz: 60, preview_max_width: 1001 });
  app.state.settings = { ...settings, preview_max_width: 1001, camera_mains_frequency_hz: 50 };
  app.populateSettings(app.state.settings, { active: "openai" });
  assert.equal(fields.namedItem("preview_max_width").value, "1001");
  assert.equal(fields.namedItem("camera_mains_frequency_hz").value, "50");
  assert.equal(Object.keys(app.settingsPayload()).length, 0);
});

function cameraMetrics(app) {
  const metrics = {};
  for (const key of ["fps", "processing", "preview-size", "model", "exposure", "gain", "lens", "flicker", "diagnostic-message", "diagnostic-warning", "diagnostic-warning-wrap"]) {
    const row = new Element({ hidden: true });
    const node = new Element({ closest: (selector) => selector === "[data-camera-diagnostic-row]" ? row : null });
    app.groups.set(`[data-camera-${key}]`, [node]);
    metrics[key] = node;
    metrics[`${key}-row`] = row;
  }
  return metrics;
}

test("camera metrics show measured values with exposure conversion and a valid infinity lens position", () => {
  const app = setup();
  const metrics = cameraMetrics(app);
  app.updateCameraMetrics({
    fps: 7.24, processing_ms: 82.38, preview_width: 800, preview_height: 450,
    camera_diagnostics: {
      backend: "picamera2", model: "imx-test", last_read_ok: true,
      requested_mains_frequency_hz: 60, applied_mains_frequency_hz: 60, warnings: [],
      frame_metadata: { ExposureTime: 8333, AnalogueGain: 2.25, LensPosition: 0 },
    },
  }, true);
  assert.equal(metrics.fps.textContent, "7.2 FPS");
  assert.equal(metrics.processing.textContent, "82.4 ms");
  assert.equal(metrics["preview-size"].textContent, "800 × 450");
  assert.equal(metrics.exposure.textContent, "8.33 ms");
  assert.equal(metrics.gain.textContent, "2.25×");
  assert.equal(metrics.lens.textContent, "0.00 D");
  assert.equal(metrics["lens-row"].hidden, false);
  assert.equal(metrics.flicker.textContent, "60 Hz");
  assert.equal(metrics["diagnostic-warning-wrap"].hidden, true);
});

test("missing or stale camera diagnostics stay unavailable without fabricated zero readings", () => {
  const app = setup();
  const metrics = cameraMetrics(app);
  app.updateCameraMetrics({ fps: 0, processing_ms: 0, preview_width: 0, preview_height: 0 }, true);
  assert.equal(metrics.fps.textContent, "측정 대기");
  assert.equal(metrics.processing.textContent, "측정 대기");
  assert.equal(metrics["preview-size"].textContent, "—");
  assert.equal(metrics["exposure-row"].hidden, true);
  assert.match(metrics["diagnostic-message"].textContent, /USB/);

  const camera = {
    fps: 7, processing_ms: 83, preview_width: 800, preview_height: 450,
    camera_diagnostics: {
      backend: "picamera2", model: "imx-test", last_read_ok: false,
      requested_mains_frequency_hz: 60, applied_mains_frequency_hz: null,
      warnings: ["AeFlickerMode unavailable"],
      frame_metadata: { ExposureTime: 10000, AnalogueGain: 2, LensPosition: 1.3 },
    },
  };
  app.updateCameraMetrics(camera, true);
  assert.equal(metrics.exposure.textContent, "");
  assert.equal(metrics["exposure-row"].hidden, true);
  assert.equal(metrics.flicker.textContent, "적용되지 않음");
  assert.equal(metrics["diagnostic-warning-wrap"].hidden, false);
  assert.match(metrics["diagnostic-warning"].textContent, /60 Hz/);
  app.updateCameraMetrics(camera, false);
  assert.equal(metrics.fps.textContent, "—");
  assert.equal(metrics["model-row"].hidden, true);
  assert.equal(metrics["diagnostic-warning-wrap"].hidden, true);
});

function inventory(app) {
  for (const id of ["inventory-table-body", "inventory-mobile", "inventory-empty", "inventory-count", "inventory-table-wrap", "inventory-range", "inventory-previous", "inventory-next"]) app.add(`#${id}`);
}

test("inventory sends all filters to the server, keeps its order and uses complete totals", async () => {
  const app = setup();
  inventory(app);
  app.add("#item-search", { value: " 오래된 물품 " });
  app.add("#status-filter", { value: "due_soon" });
  app.add("#category-filter", { value: "valuable" });
  app.add("#review-filter", { value: "needs_review" });
  app.add("#sort-filter", { value: "name" });
  const pending = app.loadItems({ offset: 48 });
  const params = new URL(app.requests[0].path, "http://localhost").searchParams;
  assert.deepEqual(Object.fromEntries(params), { status: "due_soon", q: "오래된 물품", category: "valuable", review: "needs_review", sort: "name", limit: "48", offset: "48" });
  app.requests[0].reply({ items: [item(3000, "서버 순서 첫째"), item(2, "서버 순서 둘째")], total: 5030, limit: 48, offset: 48 });
  await pending;
  assert.deepEqual(Array.from(app.state.filteredItems, (value) => value.id), [3000, 2]);
  assert.equal(app.nodes.get("#inventory-count").textContent, "5030");
  assert.equal(app.nodes.get("#inventory-range").textContent, "49–50 / 전체 5030개");
  assert.equal(app.nodes.get("#inventory-previous").disabled, false);
  assert.equal(app.nodes.get("#inventory-next").disabled, false);
  assert.match(app.nodes.get("#inventory-table-body").innerHTML, /서버 순서 첫째/);
});

test("filter resets survive polling and the server can clamp the last page after a mutation", async () => {
  const app = setup();
  inventory(app);
  app.state.itemsOffset = 96;
  const pending = app.loadItems({ resetPage: true });
  await app.loadItems({ silent: true, preserve: true });
  assert.equal(app.requests.length, 1);
  assert.equal(new URL(app.requests[0].path, "http://localhost").searchParams.get("offset"), "0");
  app.requests[0].reply({ items: [item(1)], total: 100, offset: 0, limit: 48 });
  await pending;
  const lastPage = app.loadItems({ offset: 96 });
  app.requests[1].reply({ items: [item(49)], total: 49, offset: 48, limit: 48 });
  await lastPage;
  assert.equal(app.state.itemsOffset, 48);
  assert.equal(app.nodes.get("#inventory-range").textContent, "49–49 / 전체 49개");
  assert.equal(app.nodes.get("#inventory-next").disabled, true);
});

test("a stale page response cannot overwrite the current page, total or navigation", async () => {
  const app = setup();
  inventory(app);
  const first = app.loadItems({ offset: 48 });
  const second = app.loadItems({ resetPage: true, force: true });
  app.requests[1].reply({ items: [item(10)], total: 1, offset: 0, limit: 48 });
  await second;
  app.requests[0].reply({ items: [item(20)], total: 2000, offset: 48, limit: 48 });
  await first;
  assert.equal(app.state.itemsTotal, 1);
  assert.equal(app.state.itemsOffset, 0);
  assert.equal(app.nodes.get("#inventory-next").disabled, true);
});

test("dashboard review shortcuts reset old filters and an in-flight page offset", async () => {
  const app = setup();
  for (const [id, value] of Object.entries({ "item-search": "old search", "status-filter": "disposed", "category-filter": "food", "sort-filter": "name", "review-filter": "confirmed" })) app.add(`#${id}`, { value });
  const oldPage = app.loadItems({ offset: 96 });
  const button = new Element({ dataset: { route: "items", filterReview: "needs_review", filterStatus: "holding" } });
  await app.handleDocumentClick({ target: { closest: (selector) => selector === "[data-route]" ? button : null } });
  const params = new URL(app.requests[1].path, "http://localhost").searchParams;
  assert.deepEqual(Object.fromEntries(params), { status: "holding", review: "needs_review", sort: "newest", limit: "48", offset: "0" });
  app.requests[1].reply({ items: [item(2)], total: 1, offset: 0, limit: 48 });
  await flush();
  app.requests[0].reply({ items: [item(1)], total: 200, offset: 96, limit: 48 });
  await oldPage;
  assert.equal(app.state.itemsOffset, 0);
  assert.equal(app.state.items[0].id, 2);
});

test("explicit review state takes precedence over provider compatibility labels", () => {
  const app = setup();
  assert.equal(app.reviewStatus({ provider: "pending", review_status: "confirmed" }), "confirmed");
  assert.equal(app.analysisBadgeMarkup({ provider: "offline_review", review_status: "confirmed" }), "");
  assert.match(app.analysisBadgeMarkup({ provider: "manual", review_status: "needs_review" }), /확인 필요/);
  assert.equal(app.reviewStatus({ provider: "openai_review" }), "needs_review");
  assert.equal(app.reviewStatus({ provider: "pending" }), "pending");
  assert.equal(app.effectiveStatus({ ...item(1), review_status: "dismissed" }), "dismissed");
});

test("demo labels survive manual edits and camera sources are never inferred as demo", () => {
  const app = setup();
  assert.match(app.analysisBadgeMarkup({ source_kind: "demo", provider: "manual", review_status: "confirmed" }), /시연 물품/);
  assert.doesNotMatch(app.analysisBadgeMarkup({ source_kind: "camera", provider: "mock", review_status: "confirmed" }), /시연 물품/);
  assert.match(app.analysisBadgeMarkup({ provider: "demo", review_status: "confirmed" }), /시연 물품/);
});

function detail(app, value) {
  app.add("#item-dialog", { open: true });
  app.add("#item-dialog-title");
  app.add("#item-dialog-content");
  app.state.itemDetailId = String(value.id);
  app.renderItemDetail(value);
}

test("an open read-only detail receives AI results while dirty or focused edits are preserved", async () => {
  const app = setup();
  detail(app, { ...item(1, "분석 중"), review_status: "pending" });
  const refreshed = app.refreshOpenItem();
  app.requests[0].reply({ ...item(1, "분석한 물품"), review_status: "needs_review", review_reason: "ai_rejected" });
  await refreshed;
  assert.equal(app.nodes.get("#item-dialog-title").textContent, "분석한 물품");
  assert.match(app.nodes.get("#item-dialog-content").innerHTML, /AI가 물품이 아닌 변화/);
  app.state.itemDetailDirty = true;
  await app.refreshOpenItem();
  assert.equal(app.requests.length, 1);
  app.state.itemDetailDirty = false;
  app.document.activeElement = new Element({ closest: () => new Element() });
  await app.refreshOpenItem();
  assert.equal(app.requests.length, 1);
  app.document.activeElement = null;
  const racing = app.refreshOpenItem();
  app.state.itemDetailDirty = true;
  app.requests[1].reply({ ...item(1, "뒤늦은 응답"), review_status: "confirmed" });
  await racing;
  assert.equal(app.nodes.get("#item-dialog-title").textContent, "분석한 물품");
  assert.equal(app.state.itemDetailDirty, true);
  assert.equal(app.state.itemDetailLoading, false);
});

function editForm(value, overrides = {}) {
  const fields = Object.entries({ name: value.name, category: value.category, description: value.description || "", expires_at: "2099-01-01T12:34", ...overrides }).map(([name, fieldValue]) => new Element({ name, value: fieldValue }));
  fields.namedItem = (name) => fields.find((field) => field.name === name);
  return new Element({ elements: fields, dataset: { id: String(value.id), originalCategory: value.category, originalExpiry: "2099-01-01T12:34" } });
}

test("normal edits never confirm review and explicit confirmation can save without changing fields", async () => {
  for (const confirmReview of [false, true]) {
    const app = setup();
    const original = { ...item(1), description: "", updated_at: "2026-09-18T00:00:00+00:00", review_status: "needs_review" };
    app.state.itemDetailSnapshot = original;
    const form = editForm(original, confirmReview ? {} : { name: "수정한 이름" });
    const pending = app.saveItemEdit(form, { confirmReview });
    const payload = JSON.parse(app.requests[0].options.body);
    assert.deepEqual(payload, confirmReview ? { confirm_review: true, expected_updated_at: original.updated_at } : { name: "수정한 이름", expected_updated_at: original.updated_at });
    assert.equal(form.inert, true);
    app.requests[0].reply(original);
    await flush();
    app.requests[1].reply({});
    await pending;
    assert.equal(form.inert, false);
  }
});

test("edit conflict keeps the draft and original revision until an explicit reload", async () => {
  const app = setup();
  const original = { ...item(1), description: "", updated_at: "version-before-ai", review_status: "pending" };
  detail(app, original);
  const form = editForm(original, { name: "관리자가 입력 중인 이름" });
  app.add("#item-detail-edit-notice", { hidden: true });
  const message = app.add("#item-detail-edit-message");
  const pending = app.saveItemEdit(form, { confirmReview: true });
  app.requests[0].reply({ detail: { code: "edit_conflict", message: "변경됨", item: { ...item(1, "새 AI 이름"), updated_at: "version-after-ai" } } }, 409);
  await pending;
  assert.equal(form.elements.namedItem("name").value, "관리자가 입력 중인 이름");
  assert.equal(app.state.itemDetailDirty, true);
  assert.equal(app.state.itemDetailSnapshot.updated_at, "version-before-ai");
  assert.equal(app.nodes.get("#item-detail-edit-notice").hidden, false);
  assert.match(message.textContent, /저장하지 않았습니다/);
  assert.equal(form.inert, false);
  assert.equal(app.requests.length, 1);
  const reload = app.openItem(1);
  app.requests[1].reply({ ...item(1, "새 AI 이름"), updated_at: "version-after-ai" });
  await reload;
  assert.equal(app.state.itemDetailDirty, false);
  assert.equal(app.nodes.get("#item-dialog-title").textContent, "새 AI 이름");
});

test("excluded evidence offers restoration and pending edits block lifecycle actions", async () => {
  const app = setup();
  detail(app, { ...item(1), review_status: "dismissed" });
  const markup = app.nodes.get("#item-dialog-content").innerHTML;
  assert.match(markup, /data-item-action="restore"/);
  assert.doesNotMatch(markup, /data-item-action="recover"|data-item-action="dismiss"|data-confirm-review/);
  assert.match(markup, /<form[^>]*id="item-edit-form"[^>]*hidden>/);
  app.state.itemDetailDirty = true;
  await app.handleItemAction(new Element({ dataset: { id: "1", itemAction: "restore" } }));
  assert.equal(app.requests.length, 0);
});

test("dashboard review and expiry queues are independent of the recent-items preview", () => {
  const app = setup();
  for (const id of ["attention-list", "review-panel", "review-list", "review-count", "notification-list", "notification-badge", "notification-summary"]) app.add(`#${id}`);
  app.updateDashboard({
    stats: { review_needed: 54, expired: 17, due_soon: 19 },
    items: [item(99, "최근 항목")],
    attention_items: [{ ...item(1, "오래된 만료 물품"), status: "due" }],
    review_items: [{ ...item(2, "오래된 확인 물품"), review_status: "needs_review", review_reason: "interrupted" }],
  });
  assert.match(app.nodes.get("#attention-list").innerHTML, /오래된 만료 물품/);
  assert.match(app.nodes.get("#review-list").innerHTML, /오래된 확인 물품/);
  assert.equal(app.nodes.get("#review-count").textContent, "54");
  assert.equal(app.nodes.get("#review-panel").hidden, false);
  assert.equal(app.nodes.get("#notification-badge").textContent, "90");
  assert.match(app.nodes.get("#notification-list").innerHTML, /data-filter-status="holding" data-filter-review="needs_review"/);
});

test("camera recording backpressure and inventory failures have separate operational messages", () => {
  const app = setup();
  const title = new Element();
  const notice = new Element();
  const health = new Element();
  app.groups.set('[data-motion-title]', [title]);
  app.groups.set('[data-camera-commit-notice]', [notice]);
  app.groups.set('[data-motion-health]', [health]);
  const connected = { connected: true, running: true, baseline_ready: true };
  app.updateCamera({ ...connected, phase: "commit_pending", pending_changes: 2, callback_retry_count: 1 });
  assert.equal(title.textContent, "물품 기록 반영 중");
  assert.equal(health.textContent, "기록 반영 대기");
  assert.match(notice.textContent, /2건/);
  app.updateCamera({ ...connected, phase: "inventory_unavailable", uncommitted_changes: 1 });
  assert.equal(health.textContent, "목록 연결 대기");
  assert.match(notice.textContent, /기록하지 못한 변화 1건/);
  app.updateCamera({ ...connected, phase: "monitoring" });
  assert.equal(notice.hidden, true);
});

test("a failed MJPEG connection retries after backoff while ordinary dashboard polls stay healthy", () => {
  const app = setup();
  const view = { hidden: false };
  const stream = new Element({ dataset: { streamSrc: "/camera/stream" }, closest: () => view });
  app.groups.set('[data-camera-stream], [data-camera-stream-secondary]', [stream]);
  const fallback = app.add("[data-camera-fallback]", { hidden: true });
  stream.src = "/camera/stream?t=old";
  app.setStreamHealth(stream, false);
  const failure = app.state.imageFailures.get(stream);
  assert.equal(failure.attempts, 1);
  assert.equal(fallback.hidden, false);
  app.syncCameraStreams();
  assert.equal(stream.src, "/camera/stream?t=old");
  failure.retryAt = 0;
  app.updateDashboard({ camera: { connected: true, running: true } });
  assert.notEqual(stream.src, "/camera/stream?t=old");
  assert.equal(failure.retryAt, Infinity);
  app.setStreamHealth(stream, true);
  assert.equal(app.state.imageFailures.has(stream), false);
  assert.equal(fallback.hidden, true);

  app.setStreamHealth(stream, false);
  app.state.imageFailures.get(stream).retryAt = 0;
  view.hidden = true;
  app.syncCameraStreams();
  assert.equal(stream.src, null);
  assert.equal(app.state.imageFailures.has(stream), false);
});

function failedPhoto(app) {
  const parent = new Element({ nodes: {}, getClientRects: () => [{}] });
  const placeholder = { remove() { delete parent.nodes.svg; delete parent.nodes['svg[data-image-placeholder]']; } };
  parent.insertAdjacentHTML = (_position, markup) => {
    assert.match(markup, /data-image-placeholder/);
    parent.nodes.svg = placeholder;
    parent.nodes['svg[data-image-placeholder]'] = placeholder;
  };
  const photo = new Element({ parentElement: parent, closest: () => parent });
  photo.src = "/api/items/1/image?v=original";
  app.handleImageError({ target: photo });
  return { photo, parent };
}

test("failed item photos recover without changing item data or replacing the detail form", () => {
  const app = setup();
  const { photo, parent } = failedPhoto(app);
  assert.equal(photo.isConnected, true);
  assert.equal(photo.hidden, true);
  assert.ok(parent.nodes.svg);
  const failure = app.state.imageFailures.get(photo);
  failure.retryAt = 0;
  app.updateDashboard({ items: [item(1)], stats: {} });
  const url = new URL(photo.src);
  assert.equal(url.searchParams.get("v"), "original");
  assert.ok(url.searchParams.get("retry"));
  assert.equal(failure.retryAt, Infinity);
  photo.dispatch("load");
  assert.equal(photo.hidden, false);
  assert.equal(parent.nodes.svg, undefined);
  assert.equal(app.state.imageFailures.has(photo), false);
});

test("image retries wait for visible connected views and keep a bounded backoff", () => {
  const app = setup();
  const { photo, parent } = failedPhoto(app);
  for (let index = 0; index < 10; index += 1) app.handleImageError({ target: photo });
  const failure = app.state.imageFailures.get(photo);
  assert.equal(failure.attempts, 5);
  assert.ok(failure.retryAt - Date.now() <= 30000);
  assert.ok(failure.retryAt - Date.now() > 29000);
  assert.equal(photo.events.get("load").length, 1);
  failure.retryAt = 0;
  parent.closest = (selector) => selector === "[hidden]" ? {} : null;
  app.retryFailedItemImages();
  assert.equal(photo.src, "/api/items/1/image?v=original");
  parent.closest = () => null;
  app.state.serverOnline = false;
  app.retryFailedItemImages();
  assert.equal(photo.src, "/api/items/1/image?v=original");
  app.state.serverOnline = true;
  photo.isConnected = false;
  app.retryFailedItemImages();
  assert.equal(app.state.imageFailures.has(photo), false);
});

test("a failed inventory load stays visibly failed across clock updates until a fresh response", async () => {
  const app = setup();
  inventory(app);
  const loaded = app.loadItems();
  const data = { items: [item(1)], total: 70, offset: 0, limit: 48 };
  app.requests[0].reply(data);
  await loaded;
  const failed = app.loadItems({ silent: true });
  app.requests[1].reply({ detail: "일시적인 목록 오류" }, 503);
  await failed;
  const message = app.nodes.get("#inventory-table-body").innerHTML;
  assert.match(message, /목록을 불러오지 못했습니다/);
  app.refreshItemTiming();
  assert.equal(app.nodes.get("#inventory-table-body").innerHTML, message);
  assert.equal(app.nodes.get("#inventory-count").textContent, "—");
  assert.equal(app.nodes.get("#inventory-next").disabled, true);
  const recovered = app.loadItems({ silent: true });
  app.requests[2].reply(data);
  await recovered;
  assert.equal(app.state.itemsError, null);
  assert.match(app.nodes.get("#inventory-table-body").innerHTML, /물품 1/);
  assert.equal(app.nodes.get("#inventory-count").textContent, "70");
});

test("provider configuration does not claim a successful remote connection", () => {
  const app = setup();
  const status = new Element();
  app.groups.set('[data-provider-status]', [status]);
  app.updateProvider({ active: "openai", configured: true });
  assert.equal(status.textContent, "키 설정됨");
  app.updateProvider({ active: "offline", configured: false });
  assert.equal(status.textContent, "수동 확인");
  app.updateProvider({ active: "demo", configured: true });
  assert.equal(status.textContent, "내장 시연");
});

test("built-in examples are described as simulated management actions", async () => {
  for (const action of ["add", "recover"]) {
    const app = setup();
    const toasts = app.add("#toast-region");
    const button = new Element({ dataset: { demoPreset: "phone" } });
    const pending = action === "add" ? app.runDemoPreset(button) : app.runDemoRecovery({ currentTarget: button });
    await flush();
    assert.match(button.textContent, /시연/);
    assert.doesNotMatch(button.textContent, /AI 분석|감지 중/);
    app.requests[0].reply({ ...item(1), source_kind: "demo" });
    await flush();
    app.requests[1].reply({});
    await pending;
    assert.match(toasts.children[0].innerHTML, /시연 물품/);
    assert.doesNotMatch(toasts.children[0].innerHTML, /감지했어요/);
  }
});

test("a committed edit or action permits the next operation before dashboard refresh and keeps its newer lock", async () => {
  for (const mode of ["edit", "action"]) {
    const app = setup();
    const run = (second = false) => mode === "edit"
      ? app.saveItemEdit(editForm(item(1), { name: second ? "두 번째 수정" : "첫 번째 수정" }))
      : app.handleItemAction(new Element({ dataset: { id: "1", itemAction: second ? "restore" : "recover" } }));
    const first = run();
    await flush();
    app.requests[0].reply(item(1));
    await flush();
    assert.equal(app.requests[1].path, "/api/dashboard");
    assert.equal(app.state.itemMutations.has("1"), false);
    const second = run(true);
    await flush();
    assert.equal(app.requests.length, 3);
    assert.equal(app.requests[2].options.method, mode === "edit" ? "PATCH" : "POST");
    assert.equal(app.state.itemMutations.has("1"), true);
    app.requests[1].reply({});
    await first;
    assert.equal(app.state.itemMutations.has("1"), true, "the old finally must not release the newer operation");
    await run(true);
    assert.equal(app.requests.length, 3, "an actual duplicate in-flight mutation stays blocked");
    app.requests[2].reply(item(1));
    await flush();
    app.requests[3].reply({});
    await second;
    assert.equal(app.state.itemMutations.has("1"), false);
  }
});

test("a late edit conflict for a closed item cannot dirty or alter another open item's form", async () => {
  const app = setup();
  const original = { ...item(1), updated_at: "first-revision", review_status: "pending" };
  detail(app, original);
  const saving = app.saveItemEdit(editForm(original, { name: "첫 번째 물품 편집" }));
  const opening = app.openItem(2);
  app.requests[1].reply({ ...item(2, "다른 물품"), updated_at: "second-revision" });
  await opening;
  const notice = app.add("#item-detail-edit-notice", { hidden: true });
  const message = app.add("#item-detail-edit-message", { textContent: "다른 물품 편집 안내" });
  app.requests[0].reply({ detail: { code: "edit_conflict", item: item(1, "늦게 변경된 첫 번째 물품") } }, 409);
  await saving;
  assert.equal(app.state.itemDetailId, "2");
  assert.equal(app.state.itemDetailDirty, false);
  assert.equal(app.state.itemDetailSnapshot.name, "다른 물품");
  assert.equal(notice.hidden, true);
  assert.equal(message.textContent, "다른 물품 편집 안내");
});

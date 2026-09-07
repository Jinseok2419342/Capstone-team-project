(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  const CATEGORY = {
    valuable: { label: "귀중품", days: 90 },
    general: { label: "일반 물품", days: 60 },
    food: { label: "음식물", days: 1 },
  };

  const STATUS = {
    active: { label: "보관 중", icon: "archive" },
    due_soon: { label: "폐기 임박", icon: "clock" },
    expired: { label: "기한 만료", icon: "alert" },
    recovered: { label: "회수 완료", icon: "recovered" },
    disposed: { label: "폐기 완료", icon: "trash" },
  };

  const ROUTE_TITLES = {
    dashboard: "개요",
    items: "보관 물품",
    activity: "활동 기록",
    camera: "카메라",
  };

  const ACTIVITY_META = {
    item_detected: { title: "새 물품을 감지했어요", icon: "sparkles", tone: "" },
    item_added: { title: "새 물품을 등록했어요", icon: "plus", tone: "" },
    item_classified: { title: "AI 분석을 완료했어요", icon: "sparkles", tone: "updated" },
    item_moved: { title: "물품 위치를 다시 추적했어요", icon: "refresh", tone: "updated" },
    item_recovered: { title: "물품이 회수되었어요", icon: "recovered", tone: "recovered" },
    item_disposed: { title: "물품을 폐기 처리했어요", icon: "trash", tone: "expired" },
    item_restored: { title: "물품을 보관 목록으로 복원했어요", icon: "refresh", tone: "updated" },
    item_extended: { title: "보관 기한을 연장했어요", icon: "calendar", tone: "updated" },
    item_edited: { title: "물품 정보를 수정했어요", icon: "edit", tone: "updated" },
    item_expired: { title: "보관 기한이 만료되었어요", icon: "alert", tone: "expired" },
    item_due: { title: "보관 기한이 도래했어요", icon: "alert", tone: "expired" },
    expiration_due: { title: "폐기 예정일이 도래했어요", icon: "alert", tone: "expired" },
    email_sent: { title: "관리자 메일을 발송했어요", icon: "mail", tone: "email" },
    settings_updated: { title: "시스템 설정을 변경했어요", icon: "settings", tone: "updated" },
    baseline_reset: { title: "카메라 기준 화면을 재설정했어요", icon: "camera", tone: "updated" },
    camera_connected: { title: "카메라가 연결되었어요", icon: "camera", tone: "recovered" },
    camera_disconnected: { title: "카메라 연결이 끊어졌어요", icon: "camera", tone: "expired" },
    change_ignored: { title: "오검출 후보를 제외했어요", icon: "activity", tone: "updated" },
    classification_inconclusive: { title: "AI 판정을 확인해 주세요", icon: "activity", tone: "updated" },
    recovery_check_inconclusive: { title: "회수 여부를 계속 추적하고 있어요", icon: "activity", tone: "updated" },
    recovery_check_deferred: { title: "회수 재확인을 보류했어요", icon: "activity", tone: "updated" },
  };

  const CAMERA_PHASES = {
    stopped: ["감지 중지됨", "카메라 모니터가 중지되어 있습니다."],
    starting: ["카메라 시작 중", "카메라 연결을 준비하고 있습니다."],
    opening: ["카메라 연결 중", "웹캠 연결을 기다리고 있습니다."],
    calibrating: ["기준 화면 준비 중", "화면이 안정되면 기준 화면을 자동으로 저장합니다."],
    rebaseline_pending: ["새 기준 화면 준비 중", "화면이 안정될 때까지 잠시 기다려 주세요."],
    monitoring: ["변화를 기다리는 중", "기준 화면과 현재 화면을 비교하고 있습니다."],
    settling: ["장면 안정 확인 중", "움직임이 멈춘 뒤 물품 변화를 확인합니다."],
    stabilizing: ["장면 안정 확인 중", "정확한 비교를 위해 장면이 안정됐는지 확인하고 있습니다."],
    analyzing: ["물품 변화 확인 중", "기준 화면과 안정된 장면을 비교하고 있습니다."],
    privacy: ["개인정보 보호 모드", "카메라 영상과 분석이 일시 중지되었습니다."],
    fallback: ["시연 화면 사용 중", "웹캠을 찾지 못해 안전한 대체 화면을 표시합니다."],
    offline: ["카메라 연결 대기 중", "웹캠을 찾지 못해 대체 화면을 표시하고 있습니다."],
    camera_unavailable: ["카메라를 찾을 수 없음", "연결 상태와 카메라 번호를 확인해 주세요."],
    // Older server versions used these phase names. Keep their wording
    // accurate without treating a raw frame difference as a confirmed item.
    baseline: ["기준 화면 준비 중", "화면이 안정되면 기준 화면을 자동으로 저장합니다."],
    baseline_pending: ["기준 화면 대기 중", "화면이 안정되면 기준을 자동으로 저장합니다."],
    idle: ["변화를 기다리는 중", "기준 화면과 현재 화면을 비교하고 있습니다."],
    motion: ["장면 안정 확인 중", "움직임이 멈춘 뒤 물품 변화를 확인합니다."],
    processing: ["물품 변화 확인 중", "기준 화면과 안정된 장면을 비교하고 있습니다."],
  };

  const CAMERA_PENDING_LABELS = {
    settling: "장면 안정 확인 중",
    stabilizing: "장면 안정 확인 중",
    analyzing: "물품 변화 확인 중",
    motion: "장면 안정 확인 중",
    processing: "물품 변화 확인 중",
  };

  const state = {
    route: "dashboard",
    dashboard: null,
    items: [],
    filteredItems: [],
    settings: null,
    provider: null,
    signatures: Object.create(null),
    dashboardLoading: false,
    itemsLoading: false,
    settingsLoading: false,
    requestCount: 0,
    pollTimer: null,
    itemPollTick: 0,
    serverOnline: null,
    cameraStreamHealthy: false,
    confirmResolve: null,
    resetInProgress: false,
    searchTimer: null,
    motionTimer: null,
    settingsModelCache: {},
  };

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    setTodayLabel();
    updateClocks();
    window.setInterval(updateClocks, 1000);
    bindEvents();
    setupCameraStreams();

    const route = location.hash.replace(/^#\/?/, "");
    navigate(ROUTE_TITLES[route] ? route : "dashboard", { updateHash: false, focus: false });

    if (sessionStorage.getItem("refound-demo-hint-dismissed") === "1") {
      $("#demo-hint")?.classList.add("is-dismissed");
    }

    loadDashboard({ initial: true });
    loadSettings({ populate: false, silent: true });
    startPolling();
  }

  function bindEvents() {
    document.addEventListener("click", handleDocumentClick);
    document.addEventListener("submit", handleSubmit);
    document.addEventListener("keydown", handleKeydown);
    document.addEventListener("error", handleImageError, true);

    $("#item-search")?.addEventListener("input", () => {
      window.clearTimeout(state.searchTimer);
      state.searchTimer = window.setTimeout(() => loadItems({ preserve: true }), 320);
    });
    $("#status-filter")?.addEventListener("change", () => loadItems({ preserve: true }));
    $("#category-filter")?.addEventListener("change", renderInventory);
    $("#sort-filter")?.addEventListener("change", renderInventory);

    $("#notification-button")?.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleNotifications();
    });

    $("#refresh-dashboard")?.addEventListener("click", async (event) => {
      await withButtonBusy(event.currentTarget, "새로고침 중…", () => loadDashboard({ force: true }));
    });
    $("#refresh-activity")?.addEventListener("click", async (event) => {
      await withButtonBusy(event.currentTarget, "새로고침 중…", () => loadDashboard({ force: true }));
    });
    $("#retry-connection")?.addEventListener("click", () => loadDashboard({ force: true }));
    $("#clear-filters")?.addEventListener("click", clearFilters);
    $("#test-email")?.addEventListener("click", testEmail);
    $("#demo-recover")?.addEventListener("click", runDemoRecovery);
    $("#confirm-cancel")?.addEventListener("click", () => resolveConfirmation(false));
    $("#confirm-accept")?.addEventListener("click", () => resolveConfirmation(true));

    $("#ai-provider")?.addEventListener("change", handleProviderChange);
    $("#delay-range")?.addEventListener("input", updateSettingOutputs);
    $("#threshold-range")?.addEventListener("input", updateSettingOutputs);
    $("#ai-confidence-range")?.addEventListener("input", updateSettingOutputs);
    $("#reset-confirmation")?.addEventListener("input", updateResetConfirmation);

    $$('dialog').forEach((dialog) => {
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog && !(dialog.id === "reset-dialog" && state.resetInProgress)) dialog.close();
      });
    });
    $("#confirm-dialog")?.addEventListener("close", () => {
      if (state.confirmResolve) resolveConfirmation(false, { close: false });
    });
    $("#reset-dialog")?.addEventListener("close", clearResetDialog);
    $("#reset-dialog")?.addEventListener("cancel", (event) => {
      if (state.resetInProgress) event.preventDefault();
    });

    window.addEventListener("hashchange", () => {
      const route = location.hash.replace(/^#\/?/, "");
      if (ROUTE_TITLES[route] && route !== state.route) navigate(route, { updateHash: false });
    });
    window.addEventListener("online", () => loadDashboard({ force: true }));
    window.addEventListener("offline", () => setServerConnection(false));
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) {
        loadDashboard({ force: true });
        if (state.route === "items") loadItems({ preserve: true, silent: true });
      }
    });
  }

  async function handleDocumentClick(event) {
    const routeButton = event.target.closest("[data-route]");
    if (routeButton) {
      const filter = routeButton.dataset.filterStatus;
      if (filter && $("#status-filter")) $("#status-filter").value = filter;
      navigate(routeButton.dataset.route);
      return;
    }

    if (event.target.closest("[data-open-settings]")) {
      openSettings();
      return;
    }
    if (event.target.closest("[data-open-demo]")) {
      showDialog("demo-dialog");
      return;
    }
    const closeButton = event.target.closest("[data-close-dialog]");
    if (closeButton) {
      closeDialog(closeButton.dataset.closeDialog);
      return;
    }
    if (event.target.closest("[data-close-notifications]")) {
      closeNotifications();
      return;
    }
    if (event.target.closest("[data-dismiss-demo-hint]")) {
      $("#demo-hint")?.classList.add("is-dismissed");
      sessionStorage.setItem("refound-demo-hint-dismissed", "1");
      return;
    }
    const settingsTab = event.target.closest("[data-settings-tab]");
    if (settingsTab) {
      selectSettingsTab(settingsTab.dataset.settingsTab);
      return;
    }
    if (event.target.closest("[data-reset-open]")) {
      await beginResetFlow();
      return;
    }
    const preset = event.target.closest("[data-demo-preset]");
    if (preset) {
      await runDemoPreset(preset);
      return;
    }
    if (event.target.closest("[data-rebaseline]")) {
      await rebaselineCamera();
      return;
    }
    if (event.target.closest("[data-retry-camera]")) {
      retryCameraStreams();
      return;
    }
    const actionButton = event.target.closest("[data-item-action]");
    if (actionButton) {
      await handleItemAction(actionButton);
      return;
    }
    const itemTarget = event.target.closest("[data-item-id]");
    if (itemTarget && (itemTarget.matches("button") || !event.target.closest("button, input, select, textarea, label"))) {
      openItem(itemTarget.dataset.itemId);
      return;
    }
    const toastClose = event.target.closest("[data-toast-close]");
    if (toastClose) {
      removeToast(toastClose.closest(".toast"));
      return;
    }
    if (!event.target.closest(".notification-wrap")) closeNotifications();
  }

  function handleSubmit(event) {
    if (event.target.id === "settings-form") {
      event.preventDefault();
      saveSettings();
      return;
    }
    if (event.target.id === "reset-form") {
      event.preventDefault();
      resetOperationalData();
      return;
    }
    if (event.target.id === "item-edit-form") {
      event.preventDefault();
      saveItemEdit(event.target);
    }
  }

  function handleKeydown(event) {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      navigate("items");
      window.setTimeout(() => $("#item-search")?.focus(), 80);
      return;
    }
    if (event.key === "Escape") closeNotifications();
    if ((event.key === "Enter" || event.key === " ") && event.target.matches("[data-item-id]:not(button)")) {
      event.preventDefault();
      openItem(event.target.dataset.itemId);
    }
  }

  function navigate(route, options = {}) {
    if (!ROUTE_TITLES[route]) return;
    const { updateHash = true, focus = true } = options;
    state.route = route;
    $$('[data-view]').forEach((view) => {
      const active = view.dataset.view === route;
      view.hidden = !active;
      view.classList.toggle("is-active", active);
    });
    $$(".nav-item[data-route], .mobile-nav [data-route]").forEach((button) => {
      const active = button.dataset.route === route;
      button.classList.toggle("is-active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    document.title = `${ROUTE_TITLES[route]} — Re:Found`;
    if (updateHash && location.hash !== `#${route}`) history.pushState(null, "", `#${route}`);
    closeNotifications();
    window.scrollTo({ top: 0, behavior: reduceMotion.matches ? "auto" : "smooth" });
    if (focus) $("#main-content")?.focus({ preventScroll: true });

    if (route === "items") loadItems({ preserve: state.items.length > 0 });
    if (route === "activity" && state.dashboard) renderFullActivities(state.dashboard.activities || []);
    if (route === "camera") activateSecondaryStream();
  }

  async function api(path, options = {}) {
    const { method = "GET", body, silent = false, timeout = 12000 } = options;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeout);
    if (!silent) startLoading();
    try {
      const response = await fetch(path, {
        method,
        headers: body !== undefined ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
        cache: "no-store",
      });
      let payload = null;
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) payload = await response.json();
      else {
        const text = await response.text();
        payload = text ? { message: text } : null;
      }
      if (!response.ok) {
        const error = new Error(errorMessage(payload, `요청을 처리하지 못했습니다. (${response.status})`));
        error.status = response.status;
        error.payload = payload;
        throw error;
      }
      return payload;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("서버 응답이 늦어 요청을 중단했습니다.");
      throw error;
    } finally {
      window.clearTimeout(timeoutId);
      if (!silent) finishLoading();
    }
  }

  function errorMessage(payload, fallback) {
    if (!payload) return fallback;
    if (typeof payload === "string") return payload;
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) return payload.detail.map((part) => part.msg || part.message).filter(Boolean).join(", ") || fallback;
    if (payload.detail && typeof payload.detail === "object") return payload.detail.message || payload.detail.error || fallback;
    return payload.message || payload.error || fallback;
  }

  function startLoading() {
    state.requestCount += 1;
    const bar = $("#loading-bar");
    bar?.classList.remove("is-done");
    bar?.classList.add("is-loading");
  }

  function finishLoading() {
    state.requestCount = Math.max(0, state.requestCount - 1);
    if (state.requestCount) return;
    const bar = $("#loading-bar");
    bar?.classList.remove("is-loading");
    bar?.classList.add("is-done");
    window.setTimeout(() => bar?.classList.remove("is-done"), 450);
  }

  async function loadDashboard(options = {}) {
    if (state.dashboardLoading && !options.force) return;
    state.dashboardLoading = true;
    try {
      const data = await api("/api/dashboard", { silent: !options.initial });
      if (!data || typeof data !== "object") throw new Error("대시보드 응답 형식이 올바르지 않습니다.");
      state.dashboard = data;
      updateDashboard(data);
      setServerConnection(true);
    } catch (error) {
      setServerConnection(false);
      if (options.initial || options.force) showToast("연결 오류", friendlyError(error), "error");
      if (options.initial) renderInitialFailure();
    } finally {
      state.dashboardLoading = false;
    }
  }

  function updateDashboard(data) {
    const stats = data.stats || {};
    Object.keys(STATUS).slice(0, 4).forEach((key) => {
      const target = $(`[data-stat="${key}"]`);
      if (target) animateNumber(target, finiteNumber(stats[key], 0));
    });
    const active = finiteNumber(stats.active, 0);
    if ($("#nav-active-count")) $("#nav-active-count").textContent = compactNumber(active);

    const items = normalizeItems(data.items);
    const activities = Array.isArray(data.activities) ? data.activities : [];
    const itemSignature = signature(items.map((item) => [item.id, item.name, item.status, item.expires_at, item.updated_at]));
    if (state.signatures.attention !== itemSignature) {
      renderAttention(items);
      state.signatures.attention = itemSignature;
    }
    const notificationSignature = signature([itemSignature, (data.notifications || []).map((notice) => [notice.id, notice.status, notice.error, notice.updated_at])]);
    if (state.signatures.notifications !== notificationSignature) {
      renderNotifications(items, data.notifications);
      state.signatures.notifications = notificationSignature;
    }
    const activitySignature = signature(activities.map((activity) => [activity.id, activity.type, activity.message, activity.created_at]));
    if (state.signatures.activities !== activitySignature) {
      renderActivityPreview(activities);
      renderFullActivities(activities);
      state.signatures.activities = activitySignature;
    }
    updateCamera(data.camera || {});
    updateProvider(data.provider || {});
    const sync = $("#last-sync");
    if (sync) sync.textContent = `${formatClock(new Date())} 동기화`;
  }

  function renderInitialFailure() {
    $$('[data-stat]').forEach((node) => { if (node.textContent === "—") node.textContent = "0"; });
    const attention = $("#attention-list");
    if (attention) attention.innerHTML = `<div class="attention-empty"><span><svg><use href="#icon-wifi"></use></svg></span><strong>현황을 불러오지 못했어요</strong><p>서버가 시작되면 자동으로 다시 연결합니다.</p></div>`;
    const activity = $("#activity-preview");
    if (activity) activity.innerHTML = emptyActivityMarkup("활동 기록을 불러오지 못했습니다.");
  }

  function setServerConnection(online) {
    state.serverOnline = online;
    const banner = $("#connection-banner");
    if (banner) banner.hidden = online;
    $$('[data-system-orb]').forEach((node) => {
      node.classList.toggle("is-online", online);
      node.classList.toggle("is-offline", !online);
    });
    $$('[data-system-label]').forEach((node) => { node.textContent = online ? "시스템 정상" : "서버 연결 끊김"; });
    $$('[data-system-detail]').forEach((node) => { node.textContent = online ? "모든 서비스가 동작 중입니다" : "연결을 다시 시도하고 있습니다"; });
  }

  function renderAttention(items) {
    const container = $("#attention-list");
    if (!container) return;
    const attentionItems = items
      .filter((item) => ["expired", "due_soon"].includes(effectiveStatus(item)))
      .sort((a, b) => dateValue(a.expires_at) - dateValue(b.expires_at))
      .slice(0, 4);
    if (!attentionItems.length) {
      container.innerHTML = `<div class="attention-empty"><span><svg><use href="#icon-recovered"></use></svg></span><strong>모든 물품이 여유 있어요</strong><p>7일 이내 처리할 물품이 없습니다.</p></div>`;
      return;
    }
    container.innerHTML = attentionItems.map((item) => {
      const status = effectiveStatus(item);
      return `<div class="attention-item" data-item-id="${escapeAttr(item.id)}" tabindex="0" role="button" aria-label="${escapeAttr(item.name || "물품")} 상세 보기">
        ${thumbMarkup(item)}
        <div><strong>${escapeHTML(item.name || "이름 없는 물품")}</strong><p>${escapeHTML(CATEGORY[normalizeCategory(item.category)].label)} · ${escapeHTML(formatDate(item.expires_at))}까지</p></div>
        <span class="days-left ${status === "expired" ? "is-expired" : ""}">${escapeHTML(expiryLabel(item.expires_at))}</span>
      </div>`;
    }).join("");
  }

  function renderActivityPreview(activities) {
    const container = $("#activity-preview");
    if (!container) return;
    if (!activities.length) {
      container.innerHTML = emptyActivityMarkup("아직 기록된 활동이 없습니다.");
      return;
    }
    container.innerHTML = activities.slice(0, 4).map(activityMarkup).join("");
  }

  function renderFullActivities(activities) {
    const container = $("#full-activity-list");
    if (!container) return;
    const count = $("#activity-count");
    if (count) count.textContent = activities.length ? `최근 ${activities.length}개의 시스템 활동` : "기록된 활동이 없습니다.";
    if (!activities.length) {
      container.innerHTML = `<li class="attention-empty"><span><svg><use href="#icon-activity"></use></svg></span><strong>첫 활동을 기다리고 있어요</strong><p>물품을 감지하면 이곳에 자동으로 기록됩니다.</p></li>`;
      return;
    }
    container.innerHTML = activities.map((activity) => {
      const meta = activityMeta(activity);
      return `<li class="timeline-item">
        <span class="activity-symbol ${meta.tone}"><svg><use href="#icon-${meta.icon}"></use></svg></span>
        <div><strong>${escapeHTML(meta.title)}</strong><p>${escapeHTML(activity.message || activity.description || "시스템 작업이 완료되었습니다.")}</p></div>
        <time datetime="${escapeAttr(activity.created_at || "")}">${escapeHTML(relativeTime(activity.created_at))}</time>
      </li>`;
    }).join("");
  }

  function activityMarkup(activity) {
    const meta = activityMeta(activity);
    return `<li class="activity-entry">
      <span class="activity-symbol ${meta.tone}"><svg><use href="#icon-${meta.icon}"></use></svg></span>
      <div><strong>${escapeHTML(meta.title)}</strong><p>${escapeHTML(activity.message || activity.description || "시스템 작업이 완료되었습니다.")}</p></div>
      <time datetime="${escapeAttr(activity.created_at || "")}">${escapeHTML(relativeTime(activity.created_at))}</time>
    </li>`;
  }

  function emptyActivityMarkup(message) {
    return `<li class="attention-empty"><span><svg><use href="#icon-activity"></use></svg></span><strong>표시할 활동이 없어요</strong><p>${escapeHTML(message)}</p></li>`;
  }

  function activityMeta(activity) {
    const type = String(activity.type || activity.event_type || activity.action || "").toLowerCase();
    return ACTIVITY_META[type] || { title: activity.title || "시스템 활동", icon: "activity", tone: "" };
  }

  function renderNotifications(items, serverNotifications = []) {
    const list = $("#notification-list");
    const badge = $("#notification-badge");
    const summary = $("#notification-summary");
    if (!list || !badge || !summary) return;
    const urgent = items
      .filter((item) => ["due_soon", "expired"].includes(effectiveStatus(item)))
      .sort((a, b) => dateValue(a.expires_at) - dateValue(b.expires_at));
    const failures = (Array.isArray(serverNotifications) ? serverNotifications : [])
      .filter((notice) => notice.status === "failed")
      .slice(0, 3);
    const count = urgent.length + failures.length;
    badge.hidden = count === 0;
    badge.textContent = count > 99 ? "99+" : String(count);
    summary.textContent = count ? `${count}개의 확인할 내용` : "새로운 알림이 없습니다";
    if (!count) {
      list.innerHTML = `<div class="notification-empty"><svg><use href="#icon-bell"></use></svg><span>새로운 알림이 없습니다.</span></div>`;
      return;
    }
    const itemNotices = urgent.slice(0, 8).map((item) => {
      const expired = effectiveStatus(item) === "expired";
      return `<div class="notification-item ${expired ? "is-expired" : ""}" data-item-id="${escapeAttr(item.id)}" tabindex="0" role="button">
        <span><svg><use href="#icon-${expired ? "alert" : "clock"}"></use></svg></span>
        <div><strong>${escapeHTML(item.name || "이름 없는 물품")}</strong><p>${expired ? "보관 기한이 만료되어 처리가 필요합니다." : `${expiryLabel(item.expires_at)} · ${formatDate(item.expires_at)} 만료`}</p></div>
      </div>`;
    });
    const failedNotices = failures.map((notice) => `<div class="notification-item is-expired"><span><svg><use href="#icon-mail"></use></svg></span><div><strong>메일 발송을 확인해 주세요</strong><p>${escapeHTML(notice.error || notice.message || "관리자 메일을 보내지 못했습니다.")}</p></div></div>`);
    list.innerHTML = [...itemNotices, ...failedNotices].join("");
  }

  function updateCamera(camera) {
    const connected = camera.camera_connected === true || camera.connected === true || camera.online === true;
    const fallback = camera.using_fallback === true;
    const running = camera.running !== false;
    const privacy = camera.privacy_enabled === true;
    const phase = String(camera.phase || (connected ? "monitoring" : fallback ? "fallback" : "starting"));
    const phaseInfo = CAMERA_PHASES[phase] || CAMERA_PHASES[connected ? "monitoring" : "starting"];
    const online = connected && running && !privacy;
    const displayMode = privacy ? "paused" : online ? "live" : fallback ? "demo" : "wait";
    const modeLabel = { live: "LIVE", demo: "DEMO", paused: "PAUSED", wait: "WAIT" }[displayMode];
    const pendingLabel = CAMERA_PENDING_LABELS[phase] || "";

    $$('[data-camera-dot]').forEach((node) => {
      node.classList.toggle("is-online", online);
      node.classList.toggle("is-demo", displayMode === "demo");
      node.classList.toggle("is-paused", displayMode === "paused");
      node.classList.toggle("is-offline", displayMode === "wait" && state.serverOnline === true);
    });
    $$('[data-camera-status]').forEach((node) => {
      node.textContent = privacy ? "보호 모드" : online ? "실시간" : fallback ? "대체 화면" : "연결 대기";
      const label = node.closest(".live-label");
      label?.classList.toggle("is-offline", displayMode === "wait");
      label?.classList.toggle("is-demo", displayMode === "demo");
      label?.classList.toggle("is-paused", displayMode === "paused");
    });
    $$('[data-camera-overlay]').forEach((overlay) => { overlay.dataset.mode = displayMode; });
    $$('[data-camera-mode]').forEach((node) => { node.textContent = modeLabel; });
    $$('[data-camera-message]').forEach((node) => { node.textContent = phaseInfo[1]; });
    $$('[data-motion-title]').forEach((node) => { node.textContent = phaseInfo[0]; });
    $$('[data-camera-health]').forEach((node) => { node.textContent = online ? "연결됨" : fallback ? "대체 화면" : "확인 필요"; });
    $$('[data-motion-health]').forEach((node) => {
      node.textContent = privacy ? "일시 중지" : !online ? "확인 필요" : camera.baseline_ready ? "감지 중" : "준비 중";
    });
    $$('[data-camera-name]').forEach((node) => { node.textContent = camera.name || "CAM 01"; });
    $$('[data-camera-location]').forEach((node) => { node.textContent = camera.location || "분실물 보관 구역"; });
    $$('[data-camera-delay]').forEach((node) => { node.textContent = `${formatDecimal(camera.settle_seconds ?? state.settings?.settle_seconds ?? 3)}초`; });
    $$('[data-camera-threshold]').forEach((node) => { node.textContent = sensitivityLabel(camera.motion_threshold ?? state.settings?.motion_threshold); });
    $$('[data-last-change]').forEach((node) => { node.textContent = camera.last_change_at ? relativeTime(cameraTimestamp(camera.last_change_at)) : "기록 없음"; });
    const motion = $("#motion-indicator");
    if (motion) {
      const label = motion.querySelector("[data-motion-indicator-label]");
      if (label) label.textContent = pendingLabel;
      motion.hidden = !pendingLabel;
    }
  }

  function updateProvider(provider) {
    state.provider = provider;
    const active = String(provider.active || provider.name || provider.provider || "offline").toLowerCase();
    const configured = provider.configured ?? active !== "offline";
    const display = active === "openai" ? "OpenAI" : active === "gemini" ? "Google Gemini" : active === "mock" || active === "demo" ? "시연 분석 모델" : "로컬 대체 분석";
    $$('[data-provider-name]').forEach((node) => { node.textContent = provider.model ? `${display} · ${provider.model}` : display; });
    $$('[data-provider-status]').forEach((node) => {
      node.textContent = configured ? "사용 가능" : "오프라인";
      node.classList.toggle("is-online", configured);
      node.classList.toggle("is-offline", !configured);
    });
  }

  async function loadItems(options = {}) {
    if (state.itemsLoading) return;
    state.itemsLoading = true;
    const loading = $("#inventory-loading");
    if (loading && (!options.preserve || !state.items.length)) loading.hidden = false;
    const query = $("#item-search")?.value.trim() || "";
    const uiStatus = $("#status-filter")?.value || "";
    const serverStatus = serverStatusFor(uiStatus);
    const params = new URLSearchParams();
    if (serverStatus) params.set("status", serverStatus);
    if (query) params.set("q", query);
    try {
      const data = await api(`/api/items${params.size ? `?${params}` : ""}`, { silent: options.silent === true });
      state.items = normalizeItems(data);
      renderInventory();
      if ($("#inventory-updated")) $("#inventory-updated").textContent = `${formatClock(new Date())} 업데이트`;
    } catch (error) {
      showInventoryError(friendlyError(error));
      if (!options.silent) showToast("물품을 불러오지 못했어요", friendlyError(error), "error");
    } finally {
      state.itemsLoading = false;
      if (loading) loading.hidden = true;
    }
  }

  function renderInventory() {
    const table = $("#inventory-table-body");
    const mobile = $("#inventory-mobile");
    const empty = $("#inventory-empty");
    if (!table || !mobile || !empty) return;
    const category = $("#category-filter")?.value || "";
    const uiStatus = $("#status-filter")?.value || "";
    const sort = $("#sort-filter")?.value || "newest";
    let items = state.items.filter((item) => (!category || normalizeCategory(item.category) === category) && matchesStatus(item, uiStatus));
    items = sortItems(items, sort);
    state.filteredItems = items;
    if ($("#inventory-count")) $("#inventory-count").textContent = String(items.length);

    const nextSignature = signature(items.map((item) => [item.id, item.name, item.description, item.category, item.status, item.expires_at, item.updated_at]));
    if (state.signatures.inventory === nextSignature) {
      empty.hidden = items.length !== 0;
      return;
    }
    state.signatures.inventory = nextSignature;
    empty.hidden = items.length !== 0;
    $("#inventory-table-wrap")?.toggleAttribute("hidden", items.length === 0);
    if (!items.length) {
      table.innerHTML = "";
      mobile.innerHTML = "";
      return;
    }
    table.innerHTML = items.map(tableRowMarkup).join("");
    mobile.innerHTML = items.map(mobileItemMarkup).join("");
  }

  function tableRowMarkup(item) {
    const status = effectiveStatus(item);
    const category = normalizeCategory(item.category);
    const detected = splitDate(item.detected_at);
    const expires = splitDate(item.expires_at);
    return `<tr data-item-id="${escapeAttr(item.id)}" tabindex="0" aria-label="${escapeAttr(item.name || "물품")} 상세 보기">
      <td><div class="table-item">${thumbMarkup(item)}<div><strong>${escapeHTML(item.name || "이름 없는 물품")}</strong><p>${escapeHTML(item.description || "설명이 없습니다.")}</p></div></div></td>
      <td><span class="category-badge ${category}">${CATEGORY[category].label}</span></td>
      <td class="date-cell"><strong>${escapeHTML(detected.date)}</strong><small>${escapeHTML(detected.time)}</small></td>
      <td class="date-cell"><strong>${escapeHTML(expires.date)}</strong><small>${escapeHTML(expiryLabel(item.expires_at))}</small></td>
      <td><span class="status-badge ${status}">${STATUS[status]?.label || "확인 필요"}</span></td>
      <td><button class="row-more" type="button" data-item-id="${escapeAttr(item.id)}" aria-label="${escapeAttr(item.name || "물품")} 상세 보기"><svg><use href="#icon-more"></use></svg></button></td>
    </tr>`;
  }

  function mobileItemMarkup(item) {
    const status = effectiveStatus(item);
    const category = normalizeCategory(item.category);
    return `<article class="mobile-item-card" data-item-id="${escapeAttr(item.id)}" tabindex="0" role="button" aria-label="${escapeAttr(item.name || "물품")} 상세 보기">
      ${thumbMarkup(item)}<div><h2>${escapeHTML(item.name || "이름 없는 물품")}</h2><p>${escapeHTML(formatDate(item.detected_at))} 감지 · ${escapeHTML(expiryLabel(item.expires_at))}</p><div class="mobile-badges"><span class="category-badge ${category}">${CATEGORY[category].label}</span><span class="status-badge ${status}">${STATUS[status]?.label || "확인 필요"}</span></div></div><svg><use href="#icon-chevron"></use></svg>
    </article>`;
  }

  function showInventoryError(message) {
    state.signatures.inventory = "";
    const table = $("#inventory-table-body");
    const mobile = $("#inventory-mobile");
    const empty = $("#inventory-empty");
    if (table) table.innerHTML = `<tr><td colspan="6"><div class="inline-error"><svg><use href="#icon-alert"></use></svg><strong>목록을 불러오지 못했습니다</strong><span>${escapeHTML(message)}</span><button class="button secondary compact-button" type="button" data-route="items">다시 시도</button></div></td></tr>`;
    if (mobile) mobile.innerHTML = `<div class="inline-error"><svg><use href="#icon-alert"></use></svg><strong>목록을 불러오지 못했습니다</strong><span>${escapeHTML(message)}</span><button class="button secondary compact-button" type="button" data-route="items">다시 시도</button></div>`;
    if (empty) empty.hidden = true;
  }

  function clearFilters() {
    if ($("#item-search")) $("#item-search").value = "";
    if ($("#status-filter")) $("#status-filter").value = "";
    if ($("#category-filter")) $("#category-filter").value = "";
    if ($("#sort-filter")) $("#sort-filter").value = "newest";
    loadItems();
  }

  async function openItem(id) {
    if (!id) return;
    const title = $("#item-dialog-title");
    const content = $("#item-dialog-content");
    if (title) title.textContent = "물품 정보를 불러오는 중…";
    if (content) content.innerHTML = `<div class="dialog-loading"><span class="spinner"></span><p>상세 정보를 불러오는 중…</p></div>`;
    showDialog("item-dialog");
    try {
      const item = await api(`/api/items/${encodeURIComponent(id)}`);
      renderItemDetail(item);
    } catch (error) {
      if (title) title.textContent = "물품을 열 수 없습니다";
      if (content) content.innerHTML = `<div class="dialog-error"><span><svg><use href="#icon-alert"></use></svg></span><h3>상세 정보를 불러오지 못했어요</h3><p>${escapeHTML(friendlyError(error))}</p><button class="button secondary" type="button" data-close-dialog="item-dialog">닫기</button></div>`;
    }
  }

  function renderItemDetail(item) {
    if (!item || typeof item !== "object") return;
    const title = $("#item-dialog-title");
    const content = $("#item-dialog-content");
    if (!content) return;
    if (title) title.textContent = item.name || "이름 없는 물품";
    const status = effectiveStatus(item);
    const category = normalizeCategory(item.category);
    const confidence = normalizeConfidence(item.confidence);
    const image = sanitizeImageURL(item.image_url);
    const recovered = status === "recovered";
    const disposed = status === "disposed";
    const terminal = recovered || disposed;
    content.innerHTML = `<div class="item-detail-hero">
      <div class="item-detail-image">${image ? `<img src="${escapeAttr(image)}" alt="${escapeAttr(item.name || "감지된 물품")}">` : `<svg><use href="#icon-box"></use></svg>`}</div>
      <div class="item-detail-summary">
        <div class="detail-badges"><span class="category-badge ${category}">${CATEGORY[category].label}</span><span class="status-badge ${status}">${STATUS[status]?.label || "확인 필요"}</span></div>
        <h3>${escapeHTML(item.name || "이름 없는 물품")}</h3>
        <p>${escapeHTML(item.description || "AI가 추가 설명을 제공하지 않았습니다.")}</p>
        <div class="confidence"><span>AI 신뢰도</span><div class="confidence-track"><span style="width:${confidence}%"></span></div><strong>${confidence}%</strong></div>
      </div>
    </div>
    <dl class="detail-meta">
      <div><dt>감지 시각</dt><dd>${escapeHTML(formatDateTime(item.detected_at))}</dd></div>
      <div><dt>보관 만료일</dt><dd>${escapeHTML(formatDateTime(item.expires_at))}</dd></div>
      <div><dt>기본 보관 기간</dt><dd>${escapeHTML(String(item.retention_days ?? CATEGORY[category].days))}일</dd></div>
      <div><dt>분석 제공자</dt><dd>${escapeHTML(providerLabel(item.provider))}</dd></div>
    </dl>
    <div class="detail-divider"></div>
    <form class="detail-form" id="item-edit-form" data-id="${escapeAttr(item.id)}" data-original-category="${escapeAttr(category)}" data-original-expiry="${escapeAttr(toDateTimeLocal(item.expires_at))}">
      <h3>물품 정보 편집</h3>
      <div class="field-grid">
        <label class="field"><span>물품 이름</span><input name="name" required maxlength="80" value="${escapeAttr(item.name || "")}"></label>
        <label class="field"><span>분류</span><select name="category"><option value="valuable" ${category === "valuable" ? "selected" : ""}>귀중품 · 90일</option><option value="general" ${category === "general" ? "selected" : ""}>일반 물품 · 60일</option><option value="food" ${category === "food" ? "selected" : ""}>음식물 · 1일</option></select></label>
        <label class="field full"><span>설명</span><textarea name="description" maxlength="300">${escapeHTML(item.description || "")}</textarea></label>
        <label class="field full"><span>보관 만료일</span><input name="expires_at" type="datetime-local" value="${escapeAttr(toDateTimeLocal(item.expires_at))}"><small>분류를 바꾸면 기본 보관 정책이 다시 적용됩니다.</small></label>
      </div>
      <div class="detail-form-actions"><button class="button secondary" type="submit"><svg><use href="#icon-edit"></use></svg>정보 저장</button></div>
    </form>
    <section class="detail-actions">
      <h3>보관 상태 관리</h3>
      ${terminal ? `<div class="action-row"><div><strong>보관 목록으로 복원</strong><p>${disposed ? "폐기" : "회수"} 처리를 취소하고 다시 보관 대상으로 등록합니다.</p></div><button class="button secondary" type="button" data-item-action="restore" data-id="${escapeAttr(item.id)}"><svg><use href="#icon-refresh"></use></svg>복원</button></div>` : `<div class="action-row"><div><strong>회수 완료 처리</strong><p>주인이 찾아갔거나 카메라에서 사라진 물품으로 기록합니다.</p></div><button class="button primary" type="button" data-item-action="recover" data-id="${escapeAttr(item.id)}"><svg><use href="#icon-recovered"></use></svg>회수 완료</button></div>`}
      ${terminal ? "" : `<div class="action-row"><div><strong>보관 기한 연장</strong><p>현재 만료일을 기준으로 선택한 일수만큼 연장합니다.</p></div><div class="extend-control"><input type="number" min="1" max="365" value="7" aria-label="연장 일수"><button class="button secondary" type="button" data-item-action="extend" data-id="${escapeAttr(item.id)}">연장</button></div></div><div class="action-row"><div><strong>폐기 완료 처리</strong><p>기한이 지난 물품을 보관 대상에서 제외하고 기록으로 남깁니다.</p></div><button class="button secondary" type="button" data-item-action="dispose" data-id="${escapeAttr(item.id)}"><svg><use href="#icon-trash"></use></svg>폐기 완료</button></div>`}
    </section>`;
  }

  async function saveItemEdit(form) {
    const button = $('button[type="submit"]', form);
    const values = new FormData(form);
    const localExpiry = values.get("expires_at");
    const payload = {
      name: String(values.get("name") || "").trim(),
      description: String(values.get("description") || "").trim(),
      category: String(values.get("category") || "general"),
    };
    const categoryChanged = payload.category !== form.dataset.originalCategory;
    const expiryChanged = String(localExpiry || "") !== String(form.dataset.originalExpiry || "");
    if (localExpiry && (!categoryChanged || expiryChanged)) payload.expires_at = new Date(String(localExpiry)).toISOString();
    try {
      const item = await withButtonBusy(button, "저장 중…", () => api(`/api/items/${encodeURIComponent(form.dataset.id)}`, { method: "PATCH", body: payload }));
      showToast("변경사항을 저장했어요", "물품 정보와 보관 정책을 반영했습니다.", "success");
      renderItemDetail(item);
      await refreshAfterMutation();
    } catch (error) {
      showToast("저장하지 못했어요", friendlyError(error), "error");
    }
  }

  async function handleItemAction(button) {
    const id = button.dataset.id;
    const action = button.dataset.itemAction;
    if (!id || !action) return;
    if (action === "recover") {
      const ok = await confirmAction({ title: "회수 완료로 처리할까요?", message: "이 물품은 보관 목록에서 제외되고 회수 기록으로 남습니다.", acceptLabel: "회수 완료", tone: "warning" });
      if (!ok) return;
    }
    if (action === "dispose") {
      const ok = await confirmAction({ title: "폐기 완료로 처리할까요?", message: "물품은 보관 목록에서 제외되며 활동 기록은 유지됩니다.", acceptLabel: "폐기 완료", tone: "warning" });
      if (!ok) return;
    }
    let endpoint = `/api/items/${encodeURIComponent(id)}/${action}`;
    let body;
    let busyLabel = "처리 중…";
    if (action === "extend") {
      const input = button.closest(".extend-control")?.querySelector("input");
      const days = Number(input?.value);
      if (!Number.isInteger(days) || days < 1 || days > 365) {
        showToast("연장 일수를 확인해 주세요", "1일부터 365일 사이로 입력할 수 있습니다.", "error");
        input?.focus();
        return;
      }
      body = { days };
      busyLabel = "연장 중…";
    }
    try {
      const item = await withButtonBusy(button, busyLabel, () => api(endpoint, { method: "POST", body }));
      const messages = {
        recover: ["회수 완료로 처리했어요", "물품이 회수 기록으로 이동했습니다."],
        dispose: ["폐기 완료로 처리했어요", "물품이 폐기 기록으로 이동했습니다."],
        restore: ["보관 목록으로 복원했어요", "카메라 감지 대상에 다시 포함됩니다."],
        extend: ["보관 기한을 연장했어요", `${body.days}일이 새 만료일에 반영되었습니다.`],
      };
      showToast(messages[action][0], messages[action][1], "success");
      renderItemDetail(item);
      await refreshAfterMutation();
    } catch (error) {
      if (error?.status === 409) {
        let latest = error?.payload?.detail?.item || null;
        if (!latest) {
          try {
            latest = await api(`/api/items/${encodeURIComponent(id)}`, { silent: true });
          } catch {
            latest = null;
          }
        }
        if (latest) renderItemDetail(latest);
        await refreshAfterMutation();
        showToast("물품 상태가 이미 변경됐어요", friendlyError(error), "info");
        return;
      }
      showToast("처리하지 못했어요", friendlyError(error), "error");
    }
  }

  async function runDemoPreset(button) {
    const preset = button.dataset.demoPreset;
    if (!preset) return;
    showMotionPulse();
    try {
      const item = await withButtonBusy(button, "AI 분석 중…", () => api("/api/demo/items", { method: "POST", body: { preset } }));
      closeDialog("demo-dialog");
      showToast("새 물품을 감지했어요", `${item?.name || "시연 물품"} · ${item?.retention_days || CATEGORY[normalizeCategory(item?.category)].days}일 보관`, "success");
      await refreshAfterMutation();
      if (item?.id) window.setTimeout(() => openItem(item.id), 280);
    } catch (error) {
      showToast("시연 물품을 추가하지 못했어요", friendlyError(error), "error");
    }
  }

  async function runDemoRecovery(event) {
    const button = event.currentTarget;
    const ok = await confirmAction({ title: "자동 회수를 시연할까요?", message: "가장 최근에 보관된 물품을 카메라에서 사라진 것으로 처리합니다.", acceptLabel: "회수 시연", tone: "warning" });
    if (!ok) return;
    try {
      const item = await withButtonBusy(button, "회수 감지 중…", () => api("/api/demo/recover", { method: "POST", body: {} }));
      closeDialog("demo-dialog");
      showMotionPulse();
      showToast("자동 회수를 감지했어요", `${item?.name || "최근 물품"}을 회수 완료로 처리했습니다.`, "success");
      await refreshAfterMutation();
    } catch (error) {
      showToast("회수 시연을 완료하지 못했어요", friendlyError(error), "error");
    }
  }

  function showMotionPulse() {
    const indicator = $("#motion-indicator");
    if (!indicator) return;
    const label = indicator.querySelector("[data-motion-indicator-label]");
    if (label) label.textContent = "물품 변화 확인됨";
    indicator.hidden = false;
    window.clearTimeout(state.motionTimer);
    state.motionTimer = window.setTimeout(() => { indicator.hidden = true; }, 2200);
  }

  async function refreshAfterMutation() {
    state.signatures.inventory = "";
    const operations = [loadDashboard({ force: true })];
    if (state.route === "items" || state.items.length) operations.push(loadItems({ preserve: true, silent: true }));
    await Promise.allSettled(operations);
  }

  async function openSettings() {
    showDialog("settings-dialog");
    selectSettingsTab("ai");
    await loadSettings({ populate: true });
  }

  async function loadSettings(options = {}) {
    if (state.settingsLoading) return;
    state.settingsLoading = true;
    const status = $("#settings-state");
    if (options.populate && status) status.textContent = "설정을 불러오는 중…";
    try {
      const data = await api("/api/settings", { silent: options.silent === true });
      state.settings = data?.settings || data || {};
      state.provider = data?.provider || state.provider;
      if (options.populate) populateSettings(state.settings, data?.provider || {});
      updateEmailHealth(state.settings);
      if (status) status.textContent = "";
    } catch (error) {
      if (options.populate) {
        if (status) status.textContent = "설정을 불러오지 못했습니다.";
        showToast("설정을 불러오지 못했어요", friendlyError(error), "error");
      }
    } finally {
      state.settingsLoading = false;
    }
  }

  function populateSettings(settings, provider) {
    const form = $("#settings-form");
    if (!form) return;
    const set = (name, value) => {
      const input = form.elements.namedItem(name);
      if (input && value !== undefined && value !== null) input.value = String(value);
    };
    const selectedProvider = settings.provider || provider.requested || "auto";
    set("ai_provider", selectedProvider);
    state.settingsModelCache = {
      openai: settings.openai_model || "gpt-5.6-luna",
      gemini: settings.gemini_model || "gemini-3.5-flash-lite",
    };
    const activeForModel = ["openai", "gemini"].includes(selectedProvider) ? selectedProvider : (provider.active === "gemini" ? "gemini" : "openai");
    set("ai_model", state.settingsModelCache[activeForModel]);
    set("ai_min_confidence", settings.ai_min_confidence ?? 0.5);
    set("camera_index", settings.camera_index ?? 0);
    set("motion_delay_seconds", settings.settle_seconds ?? 3);
    const threshold = Number(settings.motion_threshold);
    set("motion_threshold", Number.isFinite(threshold) ? Math.max(6, Math.min(60, Math.round(threshold))) : 20);
    set("valuable_value_threshold_krw", settings.valuable_value_threshold_krw ?? 100000);
    const privacyInput = form.elements.namedItem("privacy_mode");
    if (privacyInput) privacyInput.checked = Boolean(settings.privacy_mode);
    ["admin_email", "smtp_host", "smtp_port", "smtp_username"].forEach((key) => set(key, settings[key]));
    const openaiKey = form.elements.namedItem("openai_api_key");
    const geminiKey = form.elements.namedItem("gemini_api_key");
    const smtpKey = form.elements.namedItem("smtp_password");
    if (openaiKey) openaiKey.placeholder = settings.openai_key_configured ? "설정됨 ••••••••" : ".env 파일에서 설정";
    if (geminiKey) geminiKey.placeholder = settings.gemini_key_configured ? "설정됨 ••••••••" : ".env 파일에서 설정";
    if (smtpKey) smtpKey.placeholder = settings.smtp_password_configured ? "설정됨 ••••••••" : ".env 파일에서 설정";
    updateProviderFields();
    updateSettingOutputs();
  }

  function settingsPayload() {
    const form = $("#settings-form");
    const values = new FormData(form);
    const provider = String(values.get("ai_provider") || "auto");
    const payload = {
      provider,
      ai_min_confidence: Math.max(0.3, Math.min(0.9, Number(values.get("ai_min_confidence") || 0.5))),
      camera_index: Number(values.get("camera_index") || 0),
      settle_seconds: Number(values.get("motion_delay_seconds") || 3),
      motion_threshold: Math.max(6, Math.min(60, Number(values.get("motion_threshold") || 20))),
      privacy_mode: Boolean(form.elements.namedItem("privacy_mode")?.checked),
      admin_email: String(values.get("admin_email") || "").trim(),
      smtp_host: String(values.get("smtp_host") || "").trim(),
      smtp_port: Number(values.get("smtp_port") || 587),
      smtp_username: String(values.get("smtp_username") || "").trim(),
      valuable_value_threshold_krw: Number(values.get("valuable_value_threshold_krw") || 100000),
    };
    const model = String(values.get("ai_model") || "").trim();
    const modelProvider = ["openai", "gemini"].includes(provider) ? provider : (state.provider?.active === "gemini" ? "gemini" : "openai");
    if (model) payload[`${modelProvider}_model`] = model;
    return payload;
  }

  async function saveSettings(options = {}) {
    const button = $("#save-settings");
    const status = $("#settings-state");
    try {
      const data = await withButtonBusy(button, "저장 중…", () => api("/api/settings", { method: "PUT", body: settingsPayload() }));
      state.settings = data?.settings || data || {};
      state.provider = data?.provider || state.provider;
      if (status) status.textContent = "방금 저장됨";
      updateProvider(data?.provider || {});
      updateEmailHealth(state.settings);
      if (!options.quiet) {
        showToast("설정을 저장했어요", "카메라와 분석 시스템에 변경사항을 반영했습니다.", "success");
        closeDialog("settings-dialog");
      }
      loadDashboard({ force: true });
      return true;
    } catch (error) {
      if (status) status.textContent = "저장하지 못했습니다.";
      showToast("설정을 저장하지 못했어요", friendlyError(error), "error");
      return false;
    }
  }

  async function testEmail(event) {
    const button = event.currentTarget;
    const saved = await saveSettings({ quiet: true });
    if (!saved) return;
    try {
      const result = await withButtonBusy(button, "발송 중…", () => api("/api/settings/test-email", { method: "POST", body: {}, timeout: 30000 }));
      showToast("테스트 메일을 보냈어요", result?.message || "관리자 받은편지함을 확인해 주세요.", "success");
    } catch (error) {
      showToast("테스트 메일을 보내지 못했어요", friendlyError(error), "error");
    }
  }

  function updateEmailHealth(settings) {
    const configured = Boolean(settings?.admin_email && settings?.smtp_host && settings?.smtp_username && settings?.smtp_password_configured);
    $$('[data-email-health]').forEach((node) => { node.textContent = configured ? "설정됨" : "설정 필요"; });
  }

  function selectSettingsTab(tab) {
    $$('[data-settings-tab]').forEach((button) => button.classList.toggle("is-active", button.dataset.settingsTab === tab));
    $$('[data-settings-panel]').forEach((panel) => {
      const active = panel.dataset.settingsPanel === tab;
      panel.hidden = !active;
      panel.classList.toggle("is-active", active);
    });
  }

  async function beginResetFlow() {
    const proceed = await confirmAction({
      title: "운영 데이터를 초기화할까요?",
      message: "먼저 카메라 감시 구역의 물건을 모두 치워 주세요. 복구용 백업을 만든 뒤 물품, 활동 기록, 알림과 캡처를 비우고 빈 화면을 새 기준으로 잡습니다.",
      acceptLabel: "다음",
      tone: "danger",
    });
    if (!proceed) return;
    clearResetDialog();
    showDialog("reset-dialog");
    window.setTimeout(() => $("#reset-confirmation")?.focus(), 60);
  }

  function updateResetConfirmation() {
    const input = $("#reset-confirmation");
    const button = $("#reset-submit");
    const confirmed = input?.value.trim() === "초기화";
    if (button) button.disabled = !confirmed;
    if (confirmed && $("#reset-status")) $("#reset-status").textContent = "";
  }

  function clearResetDialog() {
    const input = $("#reset-confirmation");
    const button = $("#reset-submit");
    const status = $("#reset-status");
    const cancelButton = $("#reset-cancel");
    if (input) input.value = "";
    if (button) button.disabled = true;
    if (cancelButton) cancelButton.disabled = false;
    if (status) status.textContent = "";
  }

  async function resetOperationalData() {
    const input = $("#reset-confirmation");
    const button = $("#reset-submit");
    const status = $("#reset-status");
    const cancelButton = $("#reset-cancel");
    if (state.resetInProgress) return;
    if (input?.value.trim() !== "초기화") {
      if (status) status.textContent = "확인 문구 ‘초기화’를 정확히 입력해 주세요.";
      input?.focus();
      return;
    }
    state.resetInProgress = true;
    if (cancelButton) cancelButton.disabled = true;
    try {
      if (status) status.textContent = "백업을 만들고 운영 데이터를 초기화하는 중…";
      const result = await withButtonBusy(button, "초기화 중…", () => api("/api/maintenance/reset", {
        method: "POST",
        body: { confirmation: "초기화" },
        timeout: 300000,
      }));
      const backupPath = result?.backup_directory || result?.backup_path || result?.backup_dir || result?.backup_location || result?.backup?.path || result?.backup?.directory || result?.backup?.location || (typeof result?.backup === "string" ? result.backup : "");
      state.dashboard = null;
      state.items = [];
      state.filteredItems = [];
      state.signatures = Object.create(null);
      closeDialog("reset-dialog");
      closeDialog("settings-dialog");
      await Promise.allSettled([
        loadDashboard({ force: true }),
        loadItems({ preserve: false, silent: true }),
        loadSettings({ populate: false, silent: true }),
      ]);
      showToast("운영 데이터를 초기화했어요", backupPath ? `백업 위치: ${backupPath}` : (result?.message || "초기화 전 백업도 함께 생성했습니다."), "success", 8000);
    } catch (error) {
      const message = friendlyError(error);
      if (status) status.textContent = message;
      showToast("운영 데이터를 초기화하지 못했어요", message, "error", 7000);
      input?.focus();
    } finally {
      state.resetInProgress = false;
      if (cancelButton) cancelButton.disabled = false;
    }
  }

  function handleProviderChange() {
    const current = $("#ai-provider")?.value;
    const modelInput = $("#ai-model");
    if (modelInput && state.settingsModelCache[current]) modelInput.value = state.settingsModelCache[current];
    updateProviderFields();
  }

  function updateProviderFields() {
    const provider = $("#ai-provider")?.value || "auto";
    $$('[data-provider-key]').forEach((field) => {
      field.hidden = provider === "offline" || (provider !== "auto" && field.dataset.providerKey !== provider);
    });
    const model = $("#ai-model");
    if (model) model.disabled = provider === "offline";
  }

  function updateSettingOutputs() {
    const delay = $("#delay-range")?.value || 3;
    if ($("#delay-output")) $("#delay-output").textContent = `${delay}초`;
    const threshold = Number($("#threshold-range")?.value || 20);
    if ($("#threshold-output")) $("#threshold-output").textContent = sensitivityLabel(threshold);
    const aiConfidence = Number($("#ai-confidence-range")?.value || 0.5);
    if ($("#ai-confidence-output")) $("#ai-confidence-output").textContent = `${Math.round(aiConfidence * 100)}%`;
  }

  async function rebaselineCamera() {
    const ok = await confirmAction({ title: "기준 화면을 다시 설정할까요?", message: "현재 화면이 안정된 뒤 새 기준으로 저장됩니다. 저장된 빈 배경과 확실히 일치하는 기존 물품은 회수 처리될 수 있으니, 보관 구역과 목록을 먼저 확인해 주세요.", acceptLabel: "다시 설정", tone: "warning" });
    if (!ok) return;
    try {
      const result = await api("/api/camera/rebaseline", { method: "POST", body: {} });
      updateCamera(result?.camera || {});
      showToast("기준 화면을 재설정했어요", result?.message || "화면이 안정되면 새 기준을 자동으로 저장합니다.", "success");
      loadDashboard({ force: true });
    } catch (error) {
      showToast("기준 화면을 재설정하지 못했어요", friendlyError(error), "error");
    }
  }

  function setupCameraStreams() {
    $$('[data-camera-stream], [data-camera-stream-secondary]').forEach((image) => {
      image.addEventListener("load", () => setStreamHealth(image, true));
      image.addEventListener("error", () => setStreamHealth(image, false));
    });
  }

  function activateSecondaryStream() {
    const image = $("[data-camera-stream-secondary]");
    if (image && !image.getAttribute("src")) image.src = `${image.dataset.streamSrc}?t=${Date.now()}`;
  }

  function retryCameraStreams() {
    $$('[data-camera-fallback], [data-camera-fallback-secondary]').forEach((fallback) => { fallback.hidden = true; });
    $$('[data-camera-stream], [data-camera-stream-secondary]').forEach((image) => {
      const source = image.dataset.streamSrc || "/camera/stream";
      image.src = `${source}?t=${Date.now()}`;
    });
    showToast("카메라에 다시 연결하고 있어요", "잠시 후 실시간 화면이 표시됩니다.", "info");
  }

  function setStreamHealth(image, healthy) {
    state.cameraStreamHealthy = healthy;
    const secondary = image.hasAttribute("data-camera-stream-secondary");
    const fallback = $(secondary ? "[data-camera-fallback-secondary]" : "[data-camera-fallback]");
    if (fallback) fallback.hidden = healthy;
  }

  function handleImageError(event) {
    const image = event.target;
    if (!(image instanceof HTMLImageElement)) return;
    if (image.closest(".item-thumb, .item-detail-image")) {
      const parent = image.parentElement;
      image.remove();
      if (parent && !parent.querySelector("svg")) parent.insertAdjacentHTML("beforeend", `<svg><use href="#icon-box"></use></svg>`);
    }
  }

  function startPolling() {
    window.clearInterval(state.pollTimer);
    state.pollTimer = window.setInterval(() => {
      if (document.hidden) return;
      loadDashboard();
      state.itemPollTick += 1;
      if (state.route === "items" && state.itemPollTick % 3 === 0) loadItems({ preserve: true, silent: true });
    }, 5000);
  }

  function showDialog(id) {
    const dialog = document.getElementById(id);
    if (!(dialog instanceof HTMLDialogElement)) return;
    if (!dialog.open) dialog.showModal();
  }

  function closeDialog(id) {
    const dialog = document.getElementById(id);
    if (dialog instanceof HTMLDialogElement && dialog.open) dialog.close();
  }

  function toggleNotifications() {
    const panel = $("#notification-panel");
    const button = $("#notification-button");
    if (!panel || !button) return;
    const open = panel.hidden;
    panel.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    if (open) window.setTimeout(() => $("[data-close-notifications]")?.focus(), 0);
  }

  function closeNotifications() {
    const panel = $("#notification-panel");
    const button = $("#notification-button");
    if (panel) panel.hidden = true;
    if (button) button.setAttribute("aria-expanded", "false");
  }

  function confirmAction({ title, message, acceptLabel = "확인", tone = "info" }) {
    const dialog = $("#confirm-dialog");
    if (!(dialog instanceof HTMLDialogElement)) return Promise.resolve(window.confirm(message));
    if (state.confirmResolve) resolveConfirmation(false);
    $("#confirm-title").textContent = title;
    $("#confirm-message").textContent = message;
    $("#confirm-accept").textContent = acceptLabel;
    const icon = $("#confirm-icon");
    icon.className = `confirm-icon ${tone === "danger" ? "is-danger" : tone === "warning" ? "is-warning" : ""}`;
    icon.innerHTML = `<svg><use href="#icon-${tone === "danger" || tone === "warning" ? "alert" : "info"}"></use></svg>`;
    showDialog("confirm-dialog");
    return new Promise((resolve) => { state.confirmResolve = resolve; });
  }

  function resolveConfirmation(value, options = {}) {
    const resolver = state.confirmResolve;
    state.confirmResolve = null;
    if (options.close !== false) closeDialog("confirm-dialog");
    resolver?.(value);
  }

  function showToast(title, message = "", type = "success", duration = 4400) {
    const region = $("#toast-region");
    if (!region) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    const icon = type === "error" ? "alert" : type === "info" ? "info" : "recovered";
    toast.innerHTML = `<span><svg><use href="#icon-${icon}"></use></svg></span><div><strong>${escapeHTML(title)}</strong>${message ? `<p>${escapeHTML(message)}</p>` : ""}</div><button type="button" data-toast-close aria-label="알림 닫기"><svg><use href="#icon-close"></use></svg></button>`;
    region.appendChild(toast);
    while (region.children.length > 4) region.firstElementChild?.remove();
    window.setTimeout(() => removeToast(toast), duration);
  }

  function removeToast(toast) {
    if (!toast?.isConnected || toast.classList.contains("is-leaving")) return;
    toast.classList.add("is-leaving");
    window.setTimeout(() => toast.remove(), 230);
  }

  async function withButtonBusy(button, label, operation) {
    if (!button) return operation();
    const previous = button.innerHTML;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.textContent = label;
    try {
      return await operation();
    } finally {
      button.disabled = false;
      button.removeAttribute("aria-busy");
      button.innerHTML = previous;
    }
  }

  function normalizeItems(payload) {
    const items = Array.isArray(payload) ? payload : Array.isArray(payload?.items) ? payload.items : [];
    return items.filter((item) => item && typeof item === "object");
  }

  function normalizeCategory(value) {
    const category = String(value || "general").toLowerCase();
    if (["valuable", "expensive", "high_value", "electronics", "electronic"].includes(category)) return "valuable";
    if (["food", "beverage", "perishable", "drink"].includes(category)) return "food";
    return "general";
  }

  function effectiveStatus(item) {
    const raw = String(item?.status || "active").toLowerCase();
    if (["recovered", "returned", "collected"].includes(raw)) return "recovered";
    if (["disposed", "discarded"].includes(raw)) return "disposed";
    if (["expired", "due"].includes(raw)) return "expired";
    if (["due_soon", "expiring"].includes(raw)) return "due_soon";
    const expires = dateValue(item?.expires_at);
    if (Number.isFinite(expires)) {
      const difference = expires - Date.now();
      if (difference < 0) return "expired";
      if (difference <= 7 * 86400000) return "due_soon";
    }
    return "active";
  }

  function matchesStatus(item, filter) {
    if (!filter) return true;
    const raw = String(item?.status || "").toLowerCase();
    if (filter === "active") return ["stored", "active", "due_soon", "expiring"].includes(raw) || effectiveStatus(item) === "active" || effectiveStatus(item) === "due_soon";
    return effectiveStatus(item) === filter;
  }

  function serverStatusFor(status) {
    if (status === "active" || status === "due_soon") return "stored";
    if (status === "expired") return "due";
    if (status === "recovered") return "recovered";
    if (status === "disposed") return "disposed";
    return "";
  }

  function sortItems(items, sort) {
    const copy = [...items];
    if (sort === "expiring") return copy.sort((a, b) => dateValue(a.expires_at) - dateValue(b.expires_at));
    if (sort === "name") return copy.sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), "ko"));
    return copy.sort((a, b) => dateValue(b.detected_at) - dateValue(a.detected_at));
  }

  function sanitizeImageURL(value) {
    if (!value) return "";
    try {
      const url = new URL(String(value), location.origin);
      if (url.protocol === "data:") return url.href.startsWith("data:image/") ? url.href : "";
      return url.origin === location.origin && ["http:", "https:"].includes(url.protocol) ? url.href : "";
    } catch {
      return "";
    }
  }

  function thumbMarkup(item) {
    const url = sanitizeImageURL(item?.image_url);
    return `<div class="item-thumb">${url ? `<img src="${escapeAttr(url)}" alt="">` : `<svg><use href="#icon-box"></use></svg>`}</div>`;
  }

  function normalizeConfidence(value) {
    let number = Number(value);
    if (!Number.isFinite(number)) return 0;
    if (number <= 1) number *= 100;
    return Math.max(0, Math.min(100, Math.round(number)));
  }

  function providerLabel(value) {
    const provider = String(value || "").toLowerCase();
    if (provider.includes("openai") || provider.includes("gpt")) return "OpenAI";
    if (provider.includes("gemini") || provider.includes("google")) return "Google Gemini";
    if (provider.includes("demo") || provider.includes("mock")) return "내장 시연 모델";
    if (provider === "manual") return "관리자 수정";
    return value || "로컬 분석";
  }

  function setTodayLabel() {
    const node = $("#today-label");
    if (!node) return;
    node.textContent = new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric", weekday: "long" }).format(new Date());
  }

  function updateClocks() {
    const now = new Date();
    const text = formatClock(now, true);
    if ($("#camera-clock")) $("#camera-clock").textContent = text;
    if ($("#camera-clock-large")) $("#camera-clock-large").textContent = text;
  }

  function formatClock(date, seconds = false) {
    return new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit", ...(seconds ? { second: "2-digit" } : {}), hour12: false }).format(date);
  }

  function formatDate(value) {
    const date = parseDate(value);
    if (!date) return "날짜 미정";
    return new Intl.DateTimeFormat("ko-KR", { year: date.getFullYear() === new Date().getFullYear() ? undefined : "numeric", month: "short", day: "numeric" }).format(date);
  }

  function formatDateTime(value) {
    const date = parseDate(value);
    if (!date) return "기록 없음";
    return new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
  }

  function splitDate(value) {
    const date = parseDate(value);
    if (!date) return { date: "날짜 미정", time: "—" };
    return { date: formatDate(date), time: formatClock(date) };
  }

  function relativeTime(value) {
    const date = parseDate(value);
    if (!date) return "방금 전";
    const seconds = Math.round((date.getTime() - Date.now()) / 1000);
    const absolute = Math.abs(seconds);
    const formatter = new Intl.RelativeTimeFormat("ko", { numeric: "auto" });
    if (absolute < 60) return formatter.format(seconds, "second");
    if (absolute < 3600) return formatter.format(Math.round(seconds / 60), "minute");
    if (absolute < 86400) return formatter.format(Math.round(seconds / 3600), "hour");
    if (absolute < 604800) return formatter.format(Math.round(seconds / 86400), "day");
    return formatDate(date);
  }

  function expiryLabel(value) {
    const expires = parseDate(value);
    if (!expires) return "기한 미정";
    const difference = expires.getTime() - Date.now();
    if (difference < 0) {
      const days = Math.max(1, Math.floor(Math.abs(difference) / 86400000));
      return `${days}일 지남`;
    }
    const days = Math.ceil(difference / 86400000);
    if (days === 0) return "오늘 만료";
    return `D-${days}`;
  }

  function toDateTimeLocal(value) {
    const date = parseDate(value);
    if (!date) return "";
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  }

  function cameraTimestamp(value) {
    if (typeof value === "number") return new Date(value > 1e12 ? value : value * 1000);
    return value;
  }

  function parseDate(value) {
    if (value instanceof Date && !Number.isNaN(value.getTime())) return value;
    if (typeof value === "number") {
      const date = new Date(value > 1e12 ? value : value * 1000);
      return Number.isNaN(date.getTime()) ? null : date;
    }
    if (!value) return null;
    const date = new Date(String(value));
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function dateValue(value) {
    return parseDate(value)?.getTime() ?? Number.POSITIVE_INFINITY;
  }

  function sensitivityLabel(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "중간";
    const rounded = Math.round(number);
    const label = rounded <= 12 ? "매우 높음" : rounded <= 20 ? "높음" : rounded <= 32 ? "중간" : "낮음";
    return `${label} (${rounded})`;
  }

  function formatDecimal(value) {
    const number = Number(value);
    return Number.isInteger(number) ? String(number) : number.toFixed(1);
  }

  function animateNumber(target, value) {
    const previous = Number(target.textContent.replace(/,/g, ""));
    if (!Number.isFinite(previous) || reduceMotion.matches || previous === value) {
      target.textContent = value.toLocaleString("ko-KR");
      return;
    }
    const started = performance.now();
    const duration = 330;
    const frame = (now) => {
      const progress = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      target.textContent = Math.round(previous + (value - previous) * eased).toLocaleString("ko-KR");
      if (progress < 1) requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }

  function compactNumber(value) {
    return value > 99 ? "99+" : String(value);
  }

  function finiteNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function signature(value) {
    try { return JSON.stringify(value); } catch { return String(Date.now()); }
  }

  function friendlyError(error) {
    if (!navigator.onLine) return "인터넷 또는 로컬 네트워크 연결을 확인해 주세요.";
    const message = String(error?.message || "알 수 없는 오류가 발생했습니다.");
    if (/Failed to fetch|NetworkError|Load failed/i.test(message)) return "서버에 연결할 수 없습니다. 실행 상태를 확인해 주세요.";
    return message;
  }

  function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
  }

  function escapeAttr(value) {
    return escapeHTML(value).replace(/`/g, "&#96;");
  }
})();

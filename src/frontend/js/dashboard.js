// ── 설정 ────────────────────────────────────────────────────────────────────
const USE_MOCK = false;      // 백엔드 연동 시 false 로 변경
const AUTO_REFRESH_MS = 30000;  // 30초마다 자동 갱신 (0이면 비활성)

// ── 현재 표시 중인 항목 (처리 버튼에서 참조) ─────────────────────────────────
let _currentItems = [];

// ── 유틸 ─────────────────────────────────────────────────────────────────────
function calcDday(expiresAt) {
  const diff = new Date(expiresAt) - new Date();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function formatDatetime(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  const p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}.${p(d.getMonth()+1)}.${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function formatDate(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleDateString('ko-KR');
}

function categoryBadge(cat) {
  const map = {
    '음식물':  ['badge-food',      '음식물'],
    '비음식물': ['badge-nonfood', '비음식물'],
    '고가품':  ['badge-valuables', '고가품'],
  };
  const [cls, label] = map[cat] ?? ['', cat];
  return `<span class="badge ${cls}">${label}</span>`;
}

function ddayCell(dday) {
  if (dday < 0)  return `<span class="dday-danger">D+${Math.abs(dday)} 초과</span>`;
  if (dday === 0) return `<span class="dday-danger">D-Day</span>`;
  if (dday <= 3)  return `<span class="dday-warning">D-${dday}</span>`;
  return `<span class="dday-safe">D-${dday}</span>`;
}

function statusCell(dday) {
  return dday < 0
    ? `<span class="status-expired">폐기 필요</span>`
    : `<span class="status-active">보관 중</span>`;
}

// ── 데이터 로드 ──────────────────────────────────────────────────────────────
async function loadItems(category = 'all') {
  try {
    const items = USE_MOCK
      ? getMockItems()
      : await fetchItemsByCategory(category);
    return items;
  } catch (err) {
    console.error('데이터 로드 실패:', err);
    return null;
  }
}

// ── 요약 카드 업데이트 ───────────────────────────────────────────────────────
function updateSummaryCards(items) {
  document.getElementById('count-total').textContent     = items.length;
  document.getElementById('count-food').textContent      = items.filter(i => i.category === '음식물').length;
  document.getElementById('count-nonfood').textContent   = items.filter(i => i.category === '비음식물').length;
  document.getElementById('count-valuables').textContent = items.filter(i => i.category === '고가품').length;
}

// ── 테이블 렌더링 ────────────────────────────────────────────────────────────
function renderTable(items) {
  const tbody = document.getElementById('items-tbody');

  if (!items) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty">데이터를 불러오지 못했습니다. 백엔드 서버를 확인하세요.</td></tr>';
    return;
  }
  if (items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty">분실물이 없습니다.</td></tr>';
    return;
  }

  tbody.innerHTML = items.map(item => {
    const dday  = calcDday(item.expires_at);
    const thumb = item.image_path
      ? `<img class="thumb" src="${item.image_path}" alt="${item.name}" />`
      : '-';

    return `
      <tr>
        <td>${item.id}</td>
        <td>${item.name}</td>
        <td>${categoryBadge(item.category)}</td>
        <td>${formatDatetime(item.detected_at)}</td>
        <td>${formatDate(item.expires_at)}</td>
        <td>${ddayCell(dday)}</td>
        <td>${statusCell(dday)}</td>
        <td>${thumb}</td>
        <td><button class="btn btn-danger btn-process" data-id="${item.id}">처리</button></td>
      </tr>`;
  }).join('');
}

// ── AR 사이드바 통계 업데이트 ────────────────────────────────────────────────
function updateARSidebar(items) {
  const cats = [
    { key: 'food',      label: '음식물' },
    { key: 'nonfood',   label: '비음식물' },
    { key: 'valuables', label: '고가품' },
  ];

  let allTotal = 0, allExpired = 0;

  cats.forEach(({ key, label }) => {
    const subset  = items.filter(i => i.category === label);
    const expired = subset.filter(i => calcDday(i.expires_at) < 0).length;

    document.getElementById(`stat-${key}-total`).textContent   = subset.length;

    const expiredCell = document.getElementById(`stat-${key}-expired`);
    expiredCell.textContent = expired;
    expiredCell.className   = expired > 0 ? 'stat-expired' : '';

    allTotal   += subset.length;
    allExpired += expired;
  });

  document.getElementById('stat-all-total').textContent = allTotal;

  const allExpiredCell = document.getElementById('stat-all-expired');
  allExpiredCell.textContent = allExpired;
  allExpiredCell.className   = allExpired > 0 ? 'stat-expired' : '';
}

// ── AR 마스킹 업데이트 ───────────────────────────────────────────────────────
function updateAR(items) {
  window._arItems = items;

  // 스냅샷 이미지 설정 (백엔드 연동 시 실제 URL로 교체)
  const img = document.getElementById('camera-snapshot');
  if (!USE_MOCK) {
    const showFallback = () => {
      img.onerror = null;
      const c = document.createElement('canvas');
      c.width = 640; c.height = 480;
      const ctx = c.getContext('2d');
      ctx.fillStyle = '#1a1a2e';
      ctx.fillRect(0, 0, 640, 480);
      ctx.fillStyle = '#555';
      ctx.font = '18px sans-serif';
      ctx.fillText('카메라 스냅샷 (연결 실패)', 180, 240);
      img.src = c.toDataURL();
    };

    img.onerror = showFallback;
    img.src = getSnapshotUrl() + '?t=' + Date.now(); // 캐시 방지
  } else {
    // Mock: 빈 이미지 대신 회색 배경 Canvas를 직접 그림
    const c = document.createElement('canvas');
    c.width = 640; c.height = 480;
    const ctx = c.getContext('2d');
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, 640, 480);
    ctx.fillStyle = '#333';
    ctx.font = '18px sans-serif';
    ctx.fillText('카메라 스냅샷 (Mock)', 200, 240);
    img.src = c.toDataURL();
  }

  renderARMasks(items);
}

// ── 전체 새로고침 ────────────────────────────────────────────────────────────
async function refresh() {
  const category = document.getElementById('filter-category').value;
  const items    = await loadItems(category);

  if (items) _currentItems = items;
  if (items) updateSummaryCards(items);
  renderTable(items);
  if (items) { updateAR(items); updateARSidebar(items); }

  document.getElementById('last-updated').textContent =
    '마지막 갱신: ' + new Date().toLocaleTimeString('ko-KR');
}

// ── 이벤트 바인딩 ────────────────────────────────────────────────────────────
document.getElementById('btn-refresh').addEventListener('click', refresh);
document.getElementById('btn-refresh-ar').addEventListener('click', refresh);
document.getElementById('filter-category').addEventListener('change', refresh);

document.getElementById('items-tbody').addEventListener('click', (e) => {
  const btn = e.target.closest('.btn-process');
  if (!btn) return;
  const id   = Number(btn.dataset.id);
  const item = _currentItems.find(i => i.id === id);
  if (!item) return;
  if (!confirm(`"${item.name}" 항목을 처리(폐기)하시겠습니까?`)) return;
  _currentItems = _currentItems.filter(i => i.id !== id);
  renderTable(_currentItems);
  updateSummaryCards(_currentItems);
  updateAR(_currentItems);
  updateARSidebar(_currentItems);
});

// ── 초기 실행 ────────────────────────────────────────────────────────────────
refresh();

if (AUTO_REFRESH_MS > 0) {
  setInterval(refresh, AUTO_REFRESH_MS);
}

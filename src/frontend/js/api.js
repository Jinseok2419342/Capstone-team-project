// 백엔드 FastAPI 주소 — 실제 서버 주소로 변경하세요
const API_BASE = 'http://localhost:8000';

/**
 * 전체 분실물 목록 조회
 * GET /items
 */
async function fetchItems() {
  const res = await fetch(`${API_BASE}/items`);
  if (!res.ok) throw new Error(`API 오류: ${res.status}`);
  return res.json();
}

/**
 * 카테고리별 분실물 조회
 * GET /items?category=음식물
 */
async function fetchItemsByCategory(category) {
  const url = category === 'all'
    ? `${API_BASE}/items`
    : `${API_BASE}/items?category=${encodeURIComponent(category)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API 오류: ${res.status}`);
  const raw = await res.json();
  return raw.map(item => ({
    id:          item.id,
    name:        item.object_name,
    category:    item.category,
    detected_at: item.found_at,
    expires_at:  item.dispose_at,
    image_path:      item.image_url ?? '',
    full_image_url:  item.full_image_url ?? '',
    bbox: item.bbox ? {
      x:      item.bbox.x,
      y:      item.bbox.y,
      width:  item.bbox.w,
      height: item.bbox.h,
    } : null,
  }));
}

/**
 * 최신 카메라 스냅샷 URL
 * 백엔드에서 이미지를 제공하는 경우 사용
 */
function getSnapshotUrl() {
  return `${API_BASE}/snapshot`;
}

// ── 개발용 목(mock) 데이터 ──────────────────────────────────────────────────
// 백엔드 연동 전에 아래 함수를 fetchItems() 대신 사용하세요.
function getMockItems() {
  const now = new Date();
  const addDays = (d) => {
    const dt = new Date(now);
    dt.setDate(dt.getDate() + d);
    return dt.toISOString();
  };

  return [
    {
      id: 1,
      name: '에어팟 프로',
      category: '고가품',
      detected_at: now.toISOString(),
      expires_at: addDays(180),
      image_path: '',
      bbox: { x: 50, y: 40, width: 120, height: 90 },
    },
    {
      id: 2,
      name: '바나나',
      category: '음식물',
      detected_at: now.toISOString(),
      expires_at: addDays(-1),   // 이미 기한 초과
      image_path: '',
      bbox: { x: 200, y: 80, width: 100, height: 80 },
    },
    {
      id: 3,
      name: '우산',
      category: '비음식물',
      detected_at: now.toISOString(),
      expires_at: addDays(5),
      image_path: '',
      bbox: { x: 320, y: 60, width: 80, height: 140 },
    },
    {
      id: 4,
      name: '지갑',
      category: '고가품',
      detected_at: now.toISOString(),
      expires_at: addDays(2),
      image_path: '',
      bbox: { x: 420, y: 100, width: 90, height: 70 },
    },
  ];
}

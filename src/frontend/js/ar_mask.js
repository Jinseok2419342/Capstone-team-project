/**
 * AR 마스킹 렌더러
 * Canvas API로 분실물 bbox 위에 반투명 컬러 박스와 라벨을 그립니다.
 *
 * 색상 규칙:
 *   - 폐기 기한 초과(D-Day < 0) : 빨간색 (rgba 220,50,50,0.45)
 *   - 3일 이내 임박             : 주황색 (rgba 230,140,0,0.4)
 *   - 정상                     : 초록색 (rgba 39,174,96,0.35)
 */

const CANVAS_ID = 'ar-canvas';
const IMG_ID    = 'camera-snapshot';

function calcDday(expiresAt) {
  const diff = new Date(expiresAt) - new Date();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function maskColor(dday) {
  if (dday < 0)  return { fill: 'rgba(220,50,50,0.45)',  stroke: 'rgba(220,50,50,0.9)' };
  if (dday <= 3) return { fill: 'rgba(230,140,0,0.4)',   stroke: 'rgba(230,140,0,0.9)' };
  return             { fill: 'rgba(39,174,96,0.35)',    stroke: 'rgba(39,174,96,0.9)' };
}

/**
 * @param {Array} items  - API 응답 배열 (bbox, name, expires_at 포함)
 * @param {number} naturalW - 원본 이미지 너비(픽셀). bbox 좌표가 이 기준
 * @param {number} naturalH - 원본 이미지 높이
 */
function renderARMasks(items, naturalW = 640, naturalH = 480) {
  const canvas = document.getElementById(CANVAS_ID);
  const img    = document.getElementById(IMG_ID);
  if (!canvas) return;

  // 캔버스 크기를 표시 영역에 맞춤
  const displayW = img.clientWidth  || naturalW;
  const displayH = img.clientHeight || naturalH;
  canvas.width  = displayW;
  canvas.height = displayH;

  const scaleX = displayW / naturalW;
  const scaleY = displayH / naturalH;

  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, displayW, displayH);

  items.forEach(item => {
    if (!item.bbox) return;

    const { x, y, width, height } = item.bbox;
    const rx = x * scaleX;
    const ry = y * scaleY;
    const rw = width  * scaleX;
    const rh = height * scaleY;

    const dday  = calcDday(item.expires_at);
    const color = maskColor(dday);

    // 반투명 채우기
    ctx.fillStyle = color.fill;
    ctx.fillRect(rx, ry, rw, rh);

    // 테두리
    ctx.strokeStyle = color.stroke;
    ctx.lineWidth   = 2;
    ctx.strokeRect(rx, ry, rw, rh);

    // 라벨 배경
    const label    = `${item.name}  D${dday >= 0 ? '-' + dday : '+' + Math.abs(dday)}`;
    const fontSize = Math.max(11, Math.round(rw / 8));
    ctx.font       = `bold ${fontSize}px sans-serif`;
    const textW    = ctx.measureText(label).width + 8;
    const textH    = fontSize + 6;

    ctx.fillStyle = color.stroke;
    ctx.fillRect(rx, ry - textH, textW, textH);

    // 라벨 텍스트
    ctx.fillStyle = '#fff';
    ctx.fillText(label, rx + 4, ry - 4);
  });
}

// 이미지 로드 완료 후 마스킹 재렌더링
document.getElementById(IMG_ID)?.addEventListener('load', () => {
  if (window._arItems) renderARMasks(window._arItems);
});

// 창 크기 변경 시 재렌더링
window.addEventListener('resize', () => {
  if (window._arItems) renderARMasks(window._arItems);
});

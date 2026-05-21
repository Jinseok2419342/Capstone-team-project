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

function renderARMasks(items, naturalW = 640, naturalH = 480) {
  const canvas = document.getElementById(CANVAS_ID);
  const img    = document.getElementById(IMG_ID);
  if (!canvas) return;

  // 캔버스 픽셀 해상도를 원본 이미지 기준으로 고정
  // (CSS width:100%/height:100%가 화면 크기를 담당, 픽셀 해상도는 여기서 고정)
  canvas.width  = naturalW;
  canvas.height = naturalH;

  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, naturalW, naturalH);

  if (!items || items.length === 0) return;

  items.forEach(item => {
    if (!item.bbox) return;

    const { x, y, width, height } = item.bbox;

    const dday  = calcDday(item.expires_at);
    const color = maskColor(dday);

    ctx.fillStyle = color.fill;
    ctx.fillRect(x, y, width, height);

    ctx.strokeStyle = color.stroke;
    ctx.lineWidth   = 2;
    ctx.strokeRect(x, y, width, height);

    const label    = `${item.name}  D${dday >= 0 ? '-' + dday : '+' + Math.abs(dday)}`;
    const fontSize = Math.max(11, Math.round(width / 8));
    ctx.font       = `bold ${fontSize}px sans-serif`;
    const textW    = ctx.measureText(label).width + 8;
    const textH    = fontSize + 6;

    ctx.fillStyle = color.stroke;
    ctx.fillRect(x, y - textH, textW, textH);

    ctx.fillStyle = '#fff';
    ctx.fillText(label, x + 4, y - 4);
  });
}

// 창 크기 변경 시 재렌더링 (CSS가 크기를 담당하므로 픽셀 내용만 다시 그림)
window.addEventListener('resize', () => {
  if (window._arItems) renderARMasks(window._arItems);
});

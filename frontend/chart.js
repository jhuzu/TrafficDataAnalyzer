const FONT_STACK = 'system-ui, -apple-system, "Segoe UI", "Microsoft JhengHei", sans-serif';

export function createAnalysisChart(canvas) {
  let currentItems = [];
  let currentTitle = "";
  let resizeTimer = null;

  function draw(items = currentItems, title = currentTitle) {
    currentItems = items;
    currentTitle = title;
    if (!canvas || canvas.clientWidth === 0) return;

    const cssWidth = Math.max(canvas.clientWidth, 320);
    const cssHeight = Math.max(360, Math.min(640, 90 + items.length * 30));
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.style.height = `${cssHeight}px`;
    canvas.width = Math.round(cssWidth * ratio);
    canvas.height = Math.round(cssHeight * ratio);

    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, cssWidth, cssHeight);

    const max = Math.max(...items.map((item) => Number(item.count) || 0), 1);
    const labelWidth = Math.min(230, Math.max(120, cssWidth * 0.28));
    const valueReserve = 72;
    const availableWidth = Math.max(40, cssWidth - labelWidth - valueReserve - 24);
    const rowHeight = Math.max(24, Math.min(30, (cssHeight - 58) / Math.max(items.length, 1)));

    ctx.fillStyle = "#17324d";
    ctx.font = `700 17px ${FONT_STACK}`;
    ctx.fillText(title, 12, 26);

    items.forEach((item, index) => {
      const y = 46 + index * rowHeight;
      const count = Number(item.count) || 0;
      ctx.fillStyle = "#667085";
      ctx.font = `12px ${FONT_STACK}`;
      ctx.fillText(String(item.value).slice(0, 24), 10, y + 13, labelWidth - 18);
      const barWidth = availableWidth * count / max;
      ctx.fillStyle = "#2166a5";
      ctx.fillRect(labelWidth, y, barWidth, 17);
      ctx.fillStyle = "#17324d";
      ctx.fillText(count.toLocaleString(), labelWidth + barWidth + 6, y + 13);
    });
  }

  const observer = new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => draw(), 100);
  });
  if (canvas?.parentElement) observer.observe(canvas.parentElement);

  return {
    draw,
    clear() {
      currentItems = [];
      currentTitle = "";
      const ctx = canvas?.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    },
  };
}

// ---------------------------------------------------------------------------
// State & utilities
// ---------------------------------------------------------------------------

const state = { token: "", latest: null };

const $ = (id) => document.getElementById(id);

const esc = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

function setStatus(message) {
  $("status").textContent = message;
}

function formData() {
  const file = $("fileInput").files[0];
  if (!file) throw Error("請先選取 .xlsx 或 .xlsm 檔案。");
  const data = new FormData();
  data.append("file", file);
  return data;
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function loadData() {
  try {
    setStatus("正在辨識 Excel 資料來源…");
    const response = await fetch("/load", { method: "POST", body: formData() });
    const data = await response.json();
    if (!response.ok) throw Error(data.error);

    state.token = data.token;
    const sourceName = data.sourceType === "pivot-cache"
      ? "Pivot Cache"
      : `工作表${data.sheetName ? `「${data.sheetName}」` : ""}`;
    const countRule = data.rowMode === "raw" ? "每列按 1 件計算" : "使用「件數」欄加總";
    const warning = (data.warnings || []).join(" ");
    setStatus(`已由${sourceName}載入 ${data.rows.toLocaleString()} 筆資料；${countRule}。${warning ? ` ${warning}` : ""}`);
    await analyze();
  } catch (error) {
    setStatus(error.message);
  }
}

async function generateSlides(variant, buttonId) {
  if (!state.token) {
    $("slideStatus").textContent = "請先載入 .xlsx 或 .xlsm 檔案。";
    return;
  }
  const button = $(buttonId);
  const variantLabel = variant === "traditional" ? "傳統版本" : "新式版本";
  button.disabled = true;
  $("slideStatus").textContent = `正在生成${variantLabel}投影片…`;
  try {
    const response = await fetch("/generate-pptx", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: state.token, period: $("slidePeriod").value.trim(), variant }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw Error(data.error || "投影片生成失敗。");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `交通事故分析週報_${variantLabel}.pptx`;
    link.click();
    URL.revokeObjectURL(url);
    $("slideStatus").textContent = `已生成並下載${variantLabel}。`;
  } catch (error) {
    $("slideStatus").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Analysis
// ---------------------------------------------------------------------------

async function analyze() {
  if (!state.token) return;
  try {
    const body = {
      token: state.token,
      pattern: $("pattern").value,
      period: $("period").value,
      top: Number($("top").value),
    };
    const response = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw Error(data.error);

    state.latest = data;
    renderMetrics(data.metrics);
    renderBasic(data);
  } catch (error) {
    setStatus(error.message);
  }
}

// ---------------------------------------------------------------------------
// Rendering helpers
// ---------------------------------------------------------------------------

function renderMetrics(metrics) {
  $("metrics").innerHTML = metrics
    .map(
      (item) =>
        `<div class="metric"><small>${esc(item.label)}</small><strong>${Number(item.value).toLocaleString()}</strong></div>`,
    )
    .join("");
}

const names = {
  road: "易肇事路段",
  intersection: "易肇事路口",
  time: "易肇事時段",
  cause: "易肇事肇因",
  age: "易肇事年齡",
  vehicle: "易肇事車種",
};

function renderBasic(data) {
  const key = $("basicMetric").value;
  const items = data[key] || [];

  $("analysisTitle").textContent = names[key];
  $("analysisTable").innerHTML = items.length
    ? `<table><thead><tr><th>項目</th><th>數量</th></tr></thead><tbody>${items
        .map(
          (item) =>
            `<tr><td>${esc(item.value)}</td><td>${Number(item.count).toLocaleString()}</td></tr>`,
        )
        .join("")}</tbody></table>`
    : "<p>沒有符合資料</p>";

  drawChart(items, names[key]);
  $("trendTable").innerHTML = trendTable(data.trend);
  $("narrative").textContent = data.narrative || "";
}

function showAnalysisPanel(kind) {
  const panel = kind;
  document.querySelectorAll(".analysis-panel").forEach((item) => {
    item.classList.toggle("hidden", item.id !== `panel-${panel}`);
  });
  document.querySelectorAll(".analysis-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.analysis === kind);
  });
  if (panel === "chart" && state.latest) {
    const key = $("basicMetric").value;
    drawChart(state.latest[key] || [], names[key]);
  }
  if (panel === "map") {
    setTimeout(() => {
      if (state.token) loadHeatmap();
      if (map) map.invalidateSize();
    }, 60);
  }
}

function trendTable(items = []) {
  return `<table>
    <thead><tr><th>期間</th><th>數量</th><th>增減</th><th>增減率</th></tr></thead>
    <tbody>${items
      .map(
        (item) =>
          `<tr>
            <td>${esc(item.value)}</td>
            <td>${Number(item.count).toLocaleString()}</td>
            <td>${item.delta === null ? "—" : Number(item.delta).toLocaleString()}</td>
            <td>${item.rate === null ? "—" : (item.rate * 100).toFixed(1) + "%"}</td>
          </tr>`,
      )
      .join("")}</tbody></table>`;
}

// ---------------------------------------------------------------------------
// Canvas chart
// ---------------------------------------------------------------------------

function drawChart(items, title) {
  const canvas = $("analysisChart");
  const ctx = canvas.getContext("2d");
  const width = (canvas.width = Math.max(canvas.clientWidth, 760) * 2);
  const height = (canvas.height = 520);

  ctx.scale(2, 2);
  ctx.clearRect(0, 0, width, height);

  const max = Math.max(...items.map((item) => item.count), 1);
  const row = Math.max(22, Math.min(30, (height / 2 - 50) / Math.max(items.length, 1)));

  ctx.fillStyle = "#17324d";
  ctx.font = "bold 17px Microsoft JhengHei";
  ctx.fillText(title, 12, 24);

  items.forEach((item, index) => {
    const y = 42 + index * row;
    ctx.fillStyle = "#667085";
    ctx.font = "12px Microsoft JhengHei";
    ctx.fillText(String(item.value).slice(0, 20), 8, y + 12);

    ctx.fillStyle = "#2166a5";
    const barWidth = ((width / 2 - 200) * item.count) / max;
    ctx.fillRect(145, y, barWidth, 16);

    ctx.fillStyle = "#17324d";
    ctx.fillText(Number(item.count).toLocaleString(), 150 + barWidth, y + 12);
  });
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

function showView(id) {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("hidden", view.id !== id);
  });
  document.querySelectorAll(".nav-button[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === id);
  });
  document.querySelectorAll(".analysis-tab[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === id);
  });
}

function renderModuleNav() {
  const nav = $("moduleNav");
  const modules = window.TRAFFIC_ANALYZER_MODULES || [];
  if (!nav) return;
  nav.innerHTML = modules
    .map((module) => `<button class="nav-button${module.view === "basicView" ? " active" : ""}" data-module="${esc(module.id)}" data-view="${esc(module.view)}">${esc(module.label)}</button>`)
    .join("");
}

renderModuleNav();

// ---------------------------------------------------------------------------
// Event bindings
// ---------------------------------------------------------------------------

function clearData() {
  state.token = "";
  state.latest = null;
  $("fileInput").value = "";
  $("status").textContent = "已清除資料，請重新載入 Excel。";
  $("slideStatus").textContent = "";
  $("metrics").innerHTML = "";
  $("analysisTable").innerHTML = "<p>尚未載入資料</p>";
  $("trendTable").innerHTML = "<p>尚未載入資料</p>";
  $("narrative").textContent = "";
  $("mapInfo").textContent = "";
  $("pattern").value = "all";
  $("basicMetric").value = "road";
  $("period").value = "month";
  $("top").value = "20";
  $("slidePeriod").value = "115年1月1日至8月31日";

  const canvas = $("analysisChart");
  if (canvas) canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
  if (map) {
    if (heatLayer) {
      map.removeLayer(heatLayer);
      heatLayer = null;
    }
    if (markerLayer) markerLayer.clearLayers();
  }
  showAnalysisPanel("table");
}

$("loadButton").onclick = loadData;
$("clearButton").onclick = clearData;
$("generateModernSlidesButton").onclick = () => generateSlides("modern", "generateModernSlidesButton");
$("generateTraditionalSlidesButton").onclick = () => generateSlides("traditional", "generateTraditionalSlidesButton");
$("analyzeButton").onclick = analyze;
$("pattern").onchange = analyze;
$("period").onchange = analyze;
$("top").onchange = analyze;
$("basicMetric").onchange = () => state.latest && renderBasic(state.latest);

document.querySelectorAll(".nav-button[data-view]").forEach((button) => {
  button.onclick = () => showView(button.dataset.view);
});

document.querySelectorAll(".analysis-tab").forEach((button) => {
  button.onclick = () => {
    showAnalysisPanel(button.dataset.analysis);
  };
});

$("menuButton").onclick = () =>
  document.querySelector(".sidebar").classList.toggle("open");

$("copyButton").onclick = () =>
  navigator.clipboard
    ?.writeText($("narrative").textContent)
    .then(() => setStatus("摘要已複製。"));

// ---------------------------------------------------------------------------
// Heatmap / Map
// ---------------------------------------------------------------------------

let map = null;
let heatLayer = null;
let markerLayer = null;

function initMap() {
  if (map) return;
  const container = $("accidentMap");
  if (!container) return;

  map = L.map(container, {
    center: [25.0118, 121.459],
    zoom: 14,
    zoomControl: true,
  });

  // Use OpenStreetMap tiles (visual context only — all data stays local)
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
  }).addTo(map);

  markerLayer = L.layerGroup().addTo(map);

  // Layer toggle
  document.querySelectorAll('input[name="mapLayer"]').forEach((radio) => {
    radio.onchange = () => updateMapLayers(radio.value);
  });
}

function updateMapLayers(mode) {
  if (!map) return;
  if (heatLayer) {
    if (mode === "heat" || mode === "both") {
      map.addLayer(heatLayer);
    } else {
      map.removeLayer(heatLayer);
    }
  }
  if (markerLayer) {
    if (mode === "markers" || mode === "both") {
      map.addLayer(markerLayer);
    } else {
      map.removeLayer(markerLayer);
    }
  }
}

async function loadHeatmap() {
  if (!state.token) return;
  const container = $("accidentMap");
  if (!container || container.clientWidth === 0 || container.clientHeight === 0) return;
  initMap();
  if (!map) return;

  try {
    const body = {
      token: state.token,
      pattern: $("pattern").value,
    };
    const response = await fetch("/heatmap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) {
      $("mapInfo").textContent = data.error || "無法載入地圖資料";
      return;
    }

    // Update info
    $("mapInfo").textContent = `${data.total.toLocaleString()} 筆座標（${data.coordField}）`;

    // Clear existing layers
    if (heatLayer) {
      map.removeLayer(heatLayer);
      heatLayer = null;
    }
    markerLayer.clearLayers();

    if (data.heatPoints.length === 0) {
      $("mapInfo").textContent = "沒有可用的座標資料";
      return;
    }

    // Heat layer
    heatLayer = L.heatLayer(data.heatPoints, {
      radius: 22,
      blur: 18,
      maxZoom: 17,
      max: Math.max(...data.heatPoints.map((p) => p[2])),
      gradient: {
        0.2: "#2166a5",
        0.4: "#43a2ca",
        0.6: "#fee08b",
        0.8: "#f46d43",
        1.0: "#d73027",
      },
    }).addTo(map);

    // Marker layer — top aggregated intersections
    data.markers.forEach((m) => {
      const radius = Math.max(5, Math.min(18, Math.sqrt(m.count) * 2));
      L.circleMarker([m.lat, m.lng], {
        radius: radius,
        fillColor: "#d73027",
        color: "#fff",
        weight: 1.5,
        fillOpacity: 0.75,
      })
        .bindPopup(
          `<div class="marker-popup"><strong>${esc(m.label)}</strong><br>` +
            `事故件數：<span class="count">${m.count.toLocaleString()}</span></div>`,
        )
        .addTo(markerLayer);
    });

    // Fit map to data bounds
    const bounds = L.latLngBounds(data.heatPoints.map((p) => [p[0], p[1]]));
    map.fitBounds(bounds, { padding: [30, 30] });

    // Apply current layer toggle
    const activeRadio = document.querySelector('input[name="mapLayer"]:checked');
    updateMapLayers(activeRadio ? activeRadio.value : "heat");
  } catch (error) {
    $("mapInfo").textContent = "地圖載入失敗：" + error.message;
  }
}

// Hook into the analysis flow — load heatmap when analysis completes
const _originalAnalyze = analyze;
analyze = async function () {
  await _originalAnalyze();
  await loadHeatmap();
};

// Rebind controls after the map-enhanced analyze wrapper is installed.
$("analyzeButton").onclick = analyze;
$("pattern").onchange = analyze;
$("period").onchange = analyze;
$("top").onchange = analyze;

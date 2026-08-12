import { LatestRequest, isAbort, jsonOptions } from "./api.js";
import { createAnalysisChart } from "./chart.js";
import { createAccidentMap } from "./map.js";
import { createSlideGenerator } from "./slides.js";

const state = { token: "", latest: null, majorToken: "", majorLatest: null, performanceToken: "", majorPerformance: null, majorStatisticKeys: [] };
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#39;");

const loadRequest = new LatestRequest();
const analysisRequest = new LatestRequest();
const majorLoadRequest = new LatestRequest();
const majorAnalysisRequest = new LatestRequest();
const majorTargetRequest = new LatestRequest();
const majorPerformanceRequest = new LatestRequest();
const chart = createAnalysisChart($("analysisChart"));
const majorChart = createAnalysisChart($("majorChart"));
const accidentMap = createAccidentMap({
  container: $("accidentMap"),
  info: $("mapInfo"),
  getToken: () => state.token,
  getOptions: () => ({
    pattern: $("pattern").value,
    startDate: $("accidentStartDate").value || undefined,
    endDate: $("accidentEndDate").value || undefined,
  }),
  escapeHtml: esc,
});
const slides = createSlideGenerator({
  getToken: () => state.token,
  getPeriod: () => $("slidePeriod").value,
  status: $("slideStatus"),
});

const names = {
  road: "易肇事路段",
  intersection: "易肇事路口",
  time: "易肇事時段",
  cause: "易肇事肇因",
  age: "易肇事年齡",
  vehicle: "易肇事車種",
};

function setStatus(message) {
  $("status").textContent = message;
}

function uploadForm() {
  const file = $("fileInput").files[0];
  if (!file) throw Error("請先選取 .xlsx 或 .xlsm 檔案。");
  const form = new FormData();
  form.append("file", file);
  return form;
}

function majorUploadForm() {
  const files = Array.from($("majorFileInput").files);
  if (!files.length) throw Error("請先選取至少一份 .xlsx 或 .xlsm 檔案。");
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  return form;
}

function majorTargetUploadForm() {
  const file = $("majorTargetFileInput").files[0];
  if (!file) throw Error("請提供「績效目標值」Excel。");
  const form = new FormData();
  form.append("target", file);
  return form;
}

function majorStatisticsUploadForm() {
  const files = Array.from($("majorStatisticsFileInput").files);
  if (!files.length) throw Error("請提供至少一份統計值 Excel。");
  const form = new FormData();
  files.forEach((file) => form.append("statistics", file));
  return form;
}

async function loadData() {
  const button = $("loadButton");
  button.disabled = true;
  try {
    setStatus("正在辨識 Excel 資料來源…");
    const data = await loadRequest.json("/load", { method: "POST", body: uploadForm() });
    state.token = data.token;
    const sourceName = data.sourceType === "pivot-cache"
      ? "Pivot Cache"
      : `工作表${data.sheetName ? `「${data.sheetName}」` : ""}`;
    const countRule = data.rowMode === "raw" ? "每列按 1 件計算" : "使用「件數」欄加總";
    const warning = (data.warnings || []).join(" ");
    setStatus(`已由${sourceName}載入 ${Number(data.rows).toLocaleString()} 筆資料；${countRule}。${warning ? ` ${warning}` : ""}`);
    await analyze();
  } catch (error) {
    if (!isAbort(error)) setStatus(error.message);
  } finally {
    button.disabled = false;
  }
}

async function analyze() {
  if (!state.token) return;
  const button = $("analyzeButton");
  button.disabled = true;
  try {
    const data = await analysisRequest.json("/analyze", jsonOptions({
      token: state.token,
      pattern: $("pattern").value,
      startDate: $("accidentStartDate").value || undefined,
      endDate: $("accidentEndDate").value || undefined,
      period: $("period").value,
      top: Number($("top").value),
    }));
    state.latest = data;
    renderMetrics(data.metrics);
    renderBasic(data);
    if (!$("panel-map").classList.contains("hidden")) await accidentMap.load();
  } catch (error) {
    if (!isAbort(error)) setStatus(error.message);
  } finally {
    button.disabled = false;
  }
}

function renderMetrics(metrics) {
  $("metrics").innerHTML = metrics.map((item) =>
    `<div class="metric"><small>${esc(item.label)}</small><strong>${Number(item.value).toLocaleString()}</strong></div>`,
  ).join("");
}

function trendTable(items = []) {
  return `<table><thead><tr><th>期間</th><th>數量</th><th>增減</th><th>增減率</th></tr></thead><tbody>${items.map((item) =>
    `<tr><td>${esc(item.value)}</td><td>${Number(item.count).toLocaleString()}</td><td>${item.delta === null ? "—" : Number(item.delta).toLocaleString()}</td><td>${item.rate === null ? "—" : `${(item.rate * 100).toFixed(1)}%`}</td></tr>`,
  ).join("")}</tbody></table>`;
}

function renderBasic(data) {
  const key = $("basicMetric").value;
  const items = data[key] || [];
  $("analysisTitle").textContent = names[key];
  $("analysisTable").innerHTML = items.length
    ? `<table><thead><tr><th>項目</th><th>數量</th></tr></thead><tbody>${items.map((item) => `<tr><td>${esc(item.value)}</td><td>${Number(item.count).toLocaleString()}</td></tr>`).join("")}</tbody></table>`
    : "<p>沒有符合資料</p>";
  chart.draw(items, names[key]);
  $("trendTable").innerHTML = trendTable(data.trend);
  $("narrative").textContent = data.narrative || "";
}

function showAnalysisPanel(kind) {
  document.querySelectorAll(".analysis-panel").forEach((item) => {
    item.classList.toggle("hidden", item.id !== `panel-${kind}`);
  });
  document.querySelectorAll(".analysis-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.analysis === kind);
  });
  if (kind === "chart" && state.latest) renderBasic(state.latest);
  if (kind === "map") setTimeout(async () => {
    accidentMap.invalidate();
    await accidentMap.load();
  }, 60);
}

function showView(id) {
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("hidden", view.id !== id));
  document.querySelectorAll(".nav-button[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === id);
  });
}

function setMajorStatus(message) {
  $("majorStatus").textContent = message;
}

function renderMajorSources(sources = []) {
  $("majorSources").innerHTML = sources.length
    ? `<table><thead><tr><th>來源檔案</th><th>狀態</th><th>工作表</th><th>資料列</th><th>警告</th></tr></thead><tbody>${sources.map((source) =>
      `<tr><td>${esc(source.fileName)}</td><td>${source.status === "loaded" ? "成功" : "失敗"}</td><td>${esc(source.sheetName || "—")}</td><td>${Number(source.rows || 0).toLocaleString()}</td><td>${esc((source.warnings || []).join(" ") || "—")}</td></tr>`,
    ).join("")}</tbody></table>`
    : "";
}

function majorOptions() {
  return {
    token: state.majorToken,
    startDate: $("majorStartDate").value || undefined,
    endDate: $("majorEndDate").value || undefined,
    period: $("majorPeriod").value,
    top: Number($("majorTop").value),
  };
}

function selectedMajorCategory(data = state.majorLatest) {
  const group = $("majorGroup").value;
  return (data?.[group] || []).find((item) => item.key === $("majorCategory").value) || null;
}

function syncMajorCategories() {
  const categories = state.majorLatest?.[$("majorGroup").value] || [];
  const select = $("majorCategory");
  const prior = select.value;
  select.innerHTML = categories.map((item) =>
    `<option value="${esc(item.key)}">${esc(item.label)}${item.available ? "" : "（缺少來源）"}</option>`,
  ).join("");
  select.value = categories.some((item) => item.key === prior) ? prior : (categories[0]?.key || "");
}

function majorMetricCards(metrics) {
  const items = [
    ["期間內件數", metrics.periodCount], ["期間內資料列", metrics.periodRows],
    ["可核對重大違規", metrics.majorTotal], ["行人路權", metrics.pedestrianTotal],
  ];
  $("majorMetrics").innerHTML = items.map(([label, value]) =>
    `<div class="metric"><small>${esc(label)}</small><strong>${Number(value).toLocaleString()}</strong></div>`,
  ).join("");
}

function renderMajorAnalysis() {
  const data = state.majorLatest;
  if (!data) return;
  syncMajorCategories();
  majorMetricCards(data.metrics);
  $("majorRule").textContent = data.rule;
  const group = $("majorGroup").value;
  const categories = data[group] || [];
  $("majorCategories").innerHTML = `<table><thead><tr><th>類別</th><th>資料狀態</th><th>件數</th><th>資料列</th><th>分類依據</th></tr></thead><tbody>${categories.map((item) =>
    `<tr><td>${esc(item.label)}</td><td>${item.available ? "可核對" : "缺少來源"}</td><td>${item.available ? Number(item.count).toLocaleString() : "—"}</td><td>${item.available ? Number(item.rowCount).toLocaleString() : "—"}</td><td>${esc(item.basis)}</td></tr>`,
  ).join("")}</tbody></table>`;
  const category = selectedMajorCategory(data);
  if (!category) return;
  const metric = $("majorMetric").value;
  const metricNames = { road: "違規路段", district: "行政區", hour: "違規時段" };
  const ranking = category[metric] || [];
  $("majorRankingTitle").textContent = `${category.label}：${metricNames[metric]}排行`;
  $("majorRankingTable").innerHTML = ranking.length
    ? `<table><thead><tr><th>項目</th><th>件數</th></tr></thead><tbody>${ranking.map((item) => `<tr><td>${esc(item.value)}</td><td>${Number(item.count).toLocaleString()}</td></tr>`).join("")}</tbody></table>`
    : "<p>沒有可排行資料</p>";
  majorChart.draw(ranking, `${category.label}：${metricNames[metric]}`);
  $("majorTrendTitle").textContent = `${category.label}：${$("majorPeriod").value === "quarter" ? "季" : "月"}趨勢`;
  $("majorTrendTable").innerHTML = trendTable(category.trend);
}

async function loadMajorData() {
  const button = $("majorLoadButton");
  button.disabled = true;
  try {
    setMajorStatus("正在載入並標準化多份 Excel…");
    const data = await majorLoadRequest.json("/major-violation/load", { method: "POST", body: majorUploadForm() });
    state.majorToken = data.token;
    renderMajorSources(data.sources);
    $("majorStartDate").value = data.dateRange?.start || "";
    $("majorEndDate").value = data.dateRange?.end || "";
    const warning = (data.warnings || []).join(" ");
    setMajorStatus(`已載入 ${Number(data.rows).toLocaleString()} 列、${Number(data.totalCount).toLocaleString()} 件，來源 ${data.sources.length} 份。${warning ? ` ${warning}` : ""}`);
    await analyzeMajor();
  } catch (error) {
    if (!isAbort(error)) setMajorStatus(error.message);
  } finally {
    button.disabled = false;
  }
}

async function analyzeMajor() {
  if (!state.majorToken) return;
  const button = $("majorAnalyzeButton");
  button.disabled = true;
  try {
    const data = await majorAnalysisRequest.json("/major-violation/analyze", jsonOptions(majorOptions()));
    state.majorLatest = data;
    renderMajorAnalysis();
  } catch (error) {
    if (!isAbort(error)) setMajorStatus(error.message);
  } finally {
    button.disabled = false;
  }
}

function majorPerformanceOptions() {
  return { token: state.performanceToken, startDate: $("majorPerformanceStartDate").value || undefined, endDate: $("majorPerformanceEndDate").value || undefined, selectedKeys: Array.from(document.querySelectorAll("input[name=majorPerformanceItem]:checked")).map((item) => item.value) };
}

function renderPerformanceChoices(categories) {
  $("majorPerformanceChoices").innerHTML = categories.length ? `<strong>合計表項目</strong>${categories.map((item) => `<label><input type="checkbox" name="majorPerformanceItem" value="${esc(item.key)}" checked> ${esc(item.label)}</label>`).join("")}` : "<p>載入統計值後可選擇合計表項目。</p>";
}

function renderMajorPerformance(data) {
  state.majorPerformance = data;
  const columns = data.categories || [];
  const value = (item, kind) => kind === "target" ? Number(item.target).toLocaleString() : item.actual === null ? "待補資料" : Number(item.actual).toLocaleString();
  const rate = (item) => item.rate === null ? "—" : `${(item.rate * 100).toFixed(0)}%`;
  const totalByKey = Object.fromEntries((data.totals || []).map((item) => [item.key, item]));
  const triplet = (label, items, kind) => `<tr class="performance-${kind}"><th>${esc(label)}</th><th>${kind === "target" ? "目標值" : kind === "actual" ? "取締件數" : "達成率"}</th>${items.map((item) => `<td class="performance-cell" tabindex="0">${kind === "rate" ? rate(item) : value(item, kind)}</td>`).join("")}</tr>`;
  const unitRows = data.rows.map((row) => `${triplet(row.unit, row.cells, "target")}${triplet("", row.cells, "actual")}${triplet("", row.cells, "rate")}`).join("");
  const totals = columns.map((item) => totalByKey[item.key] || { target: 0, actual: null, rate: null });
  const totalRow = (label, kind) => `<tr class="performance-${kind}"><th colspan="2">${label}</th>${totals.map((item) => { const text = kind === "actual" ? value(item, "actual") : kind === "target" ? value(item, "target") : kind === "difference" ? item.difference === null ? "—" : Number(item.difference).toLocaleString() : rate(item); return `<td class="performance-cell" tabindex="0">${text}</td>`; }).join("")}</tr>`;
  const periodLabel = $("majorPerformancePeriod").value === "week" ? "週" : "月";
  $("majorPerformanceTable").innerHTML = `<p class="muted">目標來源：${esc(data.targetSource)}${data.statisticsSources?.length ? `；統計值來源：${data.statisticsSources.map(esc).join("、")}` : "；取締件數由重大違規原始資料計算"}。點選任一數值可標記為紅字。</p><table class="performance-table"><thead><tr><th colspan="2">項目</th>${columns.map((item) => `<th>${esc(item.label)}</th>`).join("")}</tr></thead><tbody>${unitRows}${totalRow("合計", "actual")}${totalRow(`${periodLabel}目標值`, "target")}${totalRow(`與${periodLabel}目標值差異`, "difference")}${totalRow("總達成率", "rate")}</tbody></table>${(data.warnings || []).length ? `<p class="rule-note">${data.warnings.map(esc).join("；")}</p>` : ""}`;
  $("majorPerformanceTable").querySelectorAll(".performance-cell").forEach((cell) => {
    cell.onclick = () => cell.classList.toggle("performance-marked");
    cell.onkeydown = (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); cell.classList.toggle("performance-marked"); } };
  });
}

async function loadMajorStatistics() {
  const button = $("majorStatisticsLoadButton"); button.disabled = true;
  try {
    const data = await majorTargetRequest.json("/major-violation/performance-statistics", { method: "POST", headers: { "X-Performance-Token": state.performanceToken }, body: majorStatisticsUploadForm() });
    state.performanceToken = data.token;
    state.majorStatisticKeys = data.availableKeys || [];
    const labelByKey = { red_light: "闖紅燈", speeding: "超速", wrong_way: "逆向行駛", turning: "轉彎未依規定", motorcycle_lane: "機車行駛禁行機車道", two_stage_turn: "機車未依規定兩段式左轉", parking: "併排停車與公車停靠區違規", large_vehicle: "各式大型車違規", pedestrian: "行人違規", yield_pedestrian: "汽機車不禮讓行人", helmet: "未戴安全帽", reckless: "蛇行惡意逼車" };
    renderPerformanceChoices(state.majorStatisticKeys.map((key) => ({ key, label: labelByKey[key] || key })));
    $("majorStatisticsStatus").textContent = `已載入 ${data.sourceNames.join("、")}。可選 ${state.majorStatisticKeys.length} 個項目。${(data.warnings || []).join(" ")}`;
    state.majorPerformance = null;
  } catch (error) { if (!isAbort(error)) $("majorStatisticsStatus").textContent = error.message; } finally { button.disabled = false; }
}

function saveMajorPerformanceImage() {
  const table = $("majorPerformanceTable").querySelector("table");
  if (!table || !state.majorPerformance) { $("majorPerformanceStatus").textContent = "請先產生合計表。"; return; }
  const rows = Array.from(table.rows), scale = 2, width = Math.max(900, table.scrollWidth) * scale, height = (rows.length * 34 + 70) * scale;
  const canvas = document.createElement("canvas"); canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext("2d"); ctx.scale(scale, scale); const canvasWidth = width / scale;
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvasWidth, height / scale); ctx.font = "bold 18px Microsoft JhengHei"; ctx.fillStyle = "#17324d"; ctx.fillText("重大交通違規績效合計表", 12, 26);
  const yStart = 42, rowHeight = 34, colCount = rows[0].cells.length, colWidth = canvasWidth / colCount;
  rows.forEach((row, rowIndex) => Array.from(row.cells).forEach((cell, index) => { const x = index * colWidth, y = yStart + rowIndex * rowHeight; ctx.fillStyle = rowIndex === 0 ? "#e9f2fb" : row.className.includes("rate") ? "#f6f6f6" : "#fff"; ctx.fillRect(x, y, colWidth, rowHeight); ctx.strokeStyle = "#1f2937"; ctx.strokeRect(x, y, colWidth, rowHeight); ctx.fillStyle = cell.classList.contains("performance-marked") ? "#dc2626" : "#111"; ctx.font = rowIndex === 0 || cell.tagName === "TH" ? "bold 12px Microsoft JhengHei" : "12px Microsoft JhengHei"; ctx.textAlign = "center"; ctx.fillText(cell.textContent.trim(), x + colWidth / 2, y + 22); }));
  const link = document.createElement("a"); link.download = "重大交通違規績效合計表.png"; link.href = canvas.toDataURL("image/png"); link.click();
}

async function loadMajorTargets() {
  const button = $("majorTargetLoadButton"); button.disabled = true;
  try {
    const data = await majorTargetRequest.json("/major-violation/performance-target", { method: "POST", headers: { "X-Performance-Token": state.performanceToken, "X-Performance-Period": $("majorPerformancePeriod").value }, body: majorTargetUploadForm() });
    state.performanceToken = data.token;
    $("majorTargetStatus").textContent = `已載入 ${data.sourceName}，共 ${data.units.length} 個單位。${(data.warnings || []).join(" ")}`;
    state.majorPerformance = null;
  } catch (error) { if (!isAbort(error)) $("majorTargetStatus").textContent = error.message; } finally { button.disabled = false; }
}

async function loadMajorPerformance() {
  if (!state.performanceToken) { $("majorPerformanceStatus").textContent = "請先載入績效目標值與統計值。"; return; }
  try {
    $("majorPerformanceStatus").textContent = "正在計算週報績效…";
    const data = await majorPerformanceRequest.json("/major-violation/performance", jsonOptions(majorPerformanceOptions()));
    renderMajorPerformance(data);
    $("majorPerformanceStatus").textContent = "已依目標值與目前篩選資料完成計算。";
  } catch (error) { if (!isAbort(error)) $("majorPerformanceStatus").textContent = error.message; }
}

async function generateMajorPerformanceSlides() {
  try {
    $("majorPerformanceStatus").textContent = "正在生成單頁績效投影片…";
    const blob = await majorPerformanceRequest.blob("/major-violation/generate-performance-pptx", jsonOptions(majorPerformanceOptions()));
    const url = URL.createObjectURL(blob), link = document.createElement("a");
    link.href = url; link.download = "重大交通違規績效.pptx"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
    $("majorPerformanceStatus").textContent = "已生成單頁績效投影片。";
  } catch (error) { if (!isAbort(error)) $("majorPerformanceStatus").textContent = error.message; }
}

async function clearMajorData() {
  majorLoadRequest.abort();
  majorAnalysisRequest.abort();
  if (state.majorToken) {
    try { await fetch("/clear", jsonOptions({ token: state.majorToken })); } catch (_) { /* local reset */ }
  }
  state.majorToken = "";
  state.majorLatest = null;
  $("majorFileInput").value = "";
  $("majorStartDate").value = "";
  $("majorEndDate").value = "";
  $("majorSources").innerHTML = "";
  $("majorMetrics").innerHTML = "";
  $("majorRule").textContent = "";
  $("majorCategories").innerHTML = "<p>尚未載入資料</p>";
  $("majorRankingTable").innerHTML = "<p>尚未載入資料</p>";
  $("majorTrendTable").innerHTML = "<p>尚未載入資料</p>";
  $("majorCategory").innerHTML = "";
  majorChart.clear();
  setMajorStatus("已清除重大違規資料。");
}

async function clearMajorPerformanceData() {
  majorTargetRequest.abort();
  majorPerformanceRequest.abort();
  if (state.performanceToken) {
    try { await fetch("/clear", jsonOptions({ token: state.performanceToken })); } catch (_) { /* local reset */ }
  }
  state.performanceToken = "";
  state.majorPerformance = null;
  state.majorStatisticKeys = [];
  $("majorTargetFileInput").value = "";
  $("majorStatisticsFileInput").value = "";
  $("majorPerformanceStartDate").value = "";
  $("majorPerformanceEndDate").value = "";
  $("majorTargetStatus").textContent = "";
  $("majorStatisticsStatus").textContent = "";
  $("majorPerformanceStatus").textContent = "已清除週報績效資料。";
  $("majorPerformanceChoices").innerHTML = "<p>載入統計值後可選擇合計表項目。</p>";
  $("majorPerformanceTable").innerHTML = "<p>請先載入績效目標值與統計值。</p>";
}

function showMajorPanel(kind) {
  document.querySelectorAll(".major-panel").forEach((item) => {
    item.classList.toggle("hidden", item.id !== `major-panel-${kind}`);
  });
  document.querySelectorAll("[data-major-panel]").forEach((button) => {
    button.classList.toggle("active", button.dataset.majorPanel === kind);
  });
  if (kind === "ranking" && state.majorLatest) renderMajorAnalysis();
}

function showMajorWorkspace(kind) {
  document.querySelectorAll(".major-workspace-data").forEach((item) => item.classList.toggle("hidden", kind !== "data"));
  document.querySelectorAll(".major-workspace-performance").forEach((item) => item.classList.toggle("hidden", kind !== "performance"));
  document.querySelectorAll("[data-major-workspace]").forEach((button) => button.classList.toggle("active", button.dataset.majorWorkspace === kind));
}

function renderModuleNav() {
  const nav = $("moduleNav");
  if (!nav) return;
  nav.innerHTML = (window.TRAFFIC_ANALYZER_MODULES || []).map((module) =>
    `<button class="nav-button${module.view === "basicView" ? " active" : ""}" data-module="${esc(module.id)}" data-view="${esc(module.view)}">${esc(module.label)}</button>`,
  ).join("");
  nav.querySelectorAll(".nav-button[data-view]").forEach((button) => {
    button.onclick = () => showView(button.dataset.view);
  });
}

async function clearData() {
  loadRequest.abort();
  analysisRequest.abort();
  slides.abort();
  if (state.token) {
    try {
      await fetch("/clear", jsonOptions({ token: state.token }));
    } catch (_) {
      // Local reset remains available even if the server session already expired.
    }
  }
  state.token = "";
  state.latest = null;
  $("fileInput").value = "";
  setStatus("已清除資料，請重新載入 Excel。");
  $("slideStatus").textContent = "";
  $("metrics").innerHTML = "";
  $("analysisTable").innerHTML = "<p>尚未載入資料</p>";
  $("trendTable").innerHTML = "<p>尚未載入資料</p>";
  $("narrative").textContent = "";
  $("pattern").value = "all";
  $("accidentStartDate").value = "";
  $("accidentEndDate").value = "";
  $("basicMetric").value = "road";
  $("period").value = "month";
  $("top").value = "20";
  $("slidePeriod").value = "115年1月1日至8月31日";
  chart.clear();
  accidentMap.clear();
  showAnalysisPanel("table");
}

renderModuleNav();
$("loadButton").onclick = loadData;
$("clearButton").onclick = clearData;
$("generateModernSlidesButton").onclick = () => slides.generate("modern", $("generateModernSlidesButton"));
$("generateTraditionalSlidesButton").onclick = () => slides.generate("traditional", $("generateTraditionalSlidesButton"));
$("analyzeButton").onclick = analyze;
$("pattern").onchange = analyze;
$("accidentStartDate").onchange = analyze;
$("accidentEndDate").onchange = analyze;
$("period").onchange = analyze;
$("top").onchange = analyze;
$("basicMetric").onchange = () => state.latest && renderBasic(state.latest);
document.querySelectorAll(".analysis-tab").forEach((button) => {
  button.onclick = () => showAnalysisPanel(button.dataset.analysis);
});
const menuButton = $("menuButton");
if (menuButton) {
  menuButton.onclick = () => document.querySelector(".sidebar").classList.toggle("open");
}
$("copyButton").onclick = () => navigator.clipboard?.writeText($("narrative").textContent)
  .then(() => setStatus("摘要已複製。"));
$("majorLoadButton").onclick = loadMajorData;
$("majorClearButton").onclick = clearMajorData;
$("majorPerformanceClearButton").onclick = clearMajorPerformanceData;
$("majorAnalyzeButton").onclick = analyzeMajor;
$("majorTargetLoadButton").onclick = loadMajorTargets;
$("majorStatisticsLoadButton").onclick = loadMajorStatistics;
$("majorPerformanceButton").onclick = loadMajorPerformance;
$("majorPerformanceImageButton").onclick = saveMajorPerformanceImage;
$("majorPerformanceSlidesButton").onclick = generateMajorPerformanceSlides;
$("majorGroup").onchange = () => {
  if (!state.majorLatest) return;
  renderMajorAnalysis();
};
$("majorCategory").onchange = () => {
  if (!state.majorLatest) return;
  renderMajorAnalysis();
};
$("majorMetric").onchange = () => state.majorLatest && renderMajorAnalysis();
$("majorPeriod").onchange = analyzeMajor;
$("majorTop").onchange = analyzeMajor;
document.querySelectorAll("[data-major-panel]").forEach((button) => {
  button.onclick = () => showMajorPanel(button.dataset.majorPanel);
});
document.querySelectorAll("[data-major-workspace]").forEach((button) => {
  button.onclick = () => showMajorWorkspace(button.dataset.majorWorkspace);
});

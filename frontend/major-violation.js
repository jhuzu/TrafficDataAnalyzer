import { LatestRequest, isAbort, jsonOptions } from "./api.js";
import { createAnalysisChart } from "./chart.js";
import { $, esc, state, trendTable } from "./common.js";

const labels = { red_light: "闖紅燈", speeding: "超速", wrong_way: "逆向行駛", turning: "轉彎未依規定", motorcycle_lane: "機車行駛禁行機車道", two_stage_turn: "機車未依規定兩段式左轉", parking: "併排停車與公車停靠區違規", large_vehicle: "各式大型車違規", pedestrian: "行人違規", yield_pedestrian: "汽機車不禮讓行人", helmet: "未戴安全帽", reckless: "蛇行惡意逼車" };

export function initMajorViolation() {
  const loadRequest = new LatestRequest(), analysisRequest = new LatestRequest(), targetRequest = new LatestRequest(), performanceRequest = new LatestRequest();
  const chart = createAnalysisChart($("majorChart"));
  const setStatus = (message) => { $("majorStatus").textContent = message; };
  const upload = (input, field, multiple = false) => {
    const files = multiple ? Array.from($(input).files) : [$(input).files[0]];
    if (!files.filter(Boolean).length) throw Error("請先選取 Excel 檔案。");
    const form = new FormData(); files.filter(Boolean).forEach((file) => form.append(field, file)); return form;
  };
  const options = () => ({ token: state.majorToken, startDate: $("majorStartDate").value || undefined, endDate: $("majorEndDate").value || undefined, period: $("majorPeriod").value, top: Number($("majorTop").value) });

  function renderSources(sources = []) {
    $("majorSources").innerHTML = sources.length ? `<table><thead><tr><th>來源檔案</th><th>狀態</th><th>工作表</th><th>資料列</th><th>警告</th></tr></thead><tbody>${sources.map((source) => `<tr><td>${esc(source.fileName)}</td><td>${source.status === "loaded" ? "成功" : "失敗"}</td><td>${esc(source.sheetName || "—")}</td><td>${Number(source.rows || 0).toLocaleString()}</td><td>${esc((source.warnings || []).join(" ") || "—")}</td></tr>`).join("")}</tbody></table>` : "";
  }
  function syncCategories(data) {
    const categories = data?.[$("majorGroup").value] || [], select = $("majorCategory"), prior = select.value;
    select.innerHTML = categories.map((item) => `<option value="${esc(item.key)}">${esc(item.label)}${item.available ? "" : "（缺少來源）"}</option>`).join(""); select.value = categories.some((item) => item.key === prior) ? prior : (categories[0]?.key || "");
  }
  function renderAnalysis() {
    const data = state.majorLatest; if (!data) return; syncCategories(data);
    $("majorMetrics").innerHTML = [["期間內件數", data.metrics.periodCount], ["期間內資料列", data.metrics.periodRows], ["可核對重大違規", data.metrics.majorTotal], ["行人路權", data.metrics.pedestrianTotal]].map(([label, value]) => `<div class="metric"><small>${esc(label)}</small><strong>${Number(value).toLocaleString()}</strong></div>`).join("");
    $("majorRule").textContent = data.rule; const categories = data[$("majorGroup").value] || [];
    $("majorCategories").innerHTML = `<table><thead><tr><th>類別</th><th>資料狀態</th><th>件數</th><th>資料列</th><th>分類依據</th></tr></thead><tbody>${categories.map((item) => `<tr><td>${esc(item.label)}</td><td>${item.available ? "可核對" : "缺少來源"}</td><td>${item.available ? Number(item.count).toLocaleString() : "—"}</td><td>${item.available ? Number(item.rowCount).toLocaleString() : "—"}</td><td>${esc(item.basis)}</td></tr>`).join("")}</tbody></table>`;
    const category = categories.find((item) => item.key === $("majorCategory").value); if (!category) return;
    const metric = $("majorMetric").value, metricName = { road: "違規路段", district: "行政區", hour: "違規時段" }[metric], ranking = category[metric] || [];
    $("majorRankingTitle").textContent = `${category.label}：${metricName}排行`; $("majorRankingTable").innerHTML = ranking.length ? `<table><thead><tr><th>項目</th><th>件數</th></tr></thead><tbody>${ranking.map((item) => `<tr><td>${esc(item.value)}</td><td>${Number(item.count).toLocaleString()}</td></tr>`).join("")}</tbody></table>` : "<p>沒有可排行資料</p>"; chart.draw(ranking, `${category.label}：${metricName}`); $("majorTrendTitle").textContent = `${category.label}：${$("majorPeriod").value === "quarter" ? "季" : "月"}趨勢`; $("majorTrendTable").innerHTML = trendTable(category.trend);
  }
  async function loadData() {
    const button = $("majorLoadButton"); button.disabled = true;
    try { setStatus("正在載入並標準化多份 Excel…"); const data = await loadRequest.json("/major-violation/load", { method: "POST", body: upload("majorFileInput", "files", true) }); state.majorToken = data.token; renderSources(data.sources); $("majorStartDate").value = data.dateRange?.start || ""; $("majorEndDate").value = data.dateRange?.end || ""; setStatus(`已載入 ${Number(data.rows).toLocaleString()} 列、${Number(data.totalCount).toLocaleString()} 件，來源 ${data.sources.length} 份。${(data.warnings || []).join(" ")}`); await analyze(); } catch (error) { if (!isAbort(error)) setStatus(error.message); } finally { button.disabled = false; }
  }
  async function analyze() {
    if (!state.majorToken) return; const button = $("majorAnalyzeButton"); button.disabled = true;
    try { state.majorLatest = await analysisRequest.json("/major-violation/analyze", jsonOptions(options())); renderAnalysis(); } catch (error) { if (!isAbort(error)) setStatus(error.message); } finally { button.disabled = false; }
  }
  function performanceOptions() { return { token: state.performanceToken, startDate: $("majorPerformanceStartDate").value || undefined, endDate: $("majorPerformanceEndDate").value || undefined, selectedKeys: Array.from(document.querySelectorAll("input[name=majorPerformanceItem]:checked")).map((item) => item.value) }; }
  function renderChoices(keys) { $("majorPerformanceChoices").innerHTML = keys.length ? `<strong>合計表項目</strong>${keys.map((key) => `<label><input type="checkbox" name="majorPerformanceItem" value="${esc(key)}" checked> ${esc(labels[key] || key)}</label>`).join("")}` : "<p>載入統計值後可選擇合計表項目。</p>"; }
  function renderPerformance(data) {
    state.majorPerformance = data; const columns = data.categories || [], totals = Object.fromEntries((data.totals || []).map((item) => [item.key, item]));
    const value = (item, kind) => kind === "target" ? Number(item.target).toLocaleString() : item.actual === null ? "待補資料" : Number(item.actual).toLocaleString(); const rate = (item) => item.rate === null ? "—" : `${(item.rate * 100).toFixed(0)}%`;
    const triplet = (label, items, kind) => `<tr class="performance-${kind}"><th>${esc(label)}</th><th>${kind === "target" ? "目標值" : kind === "actual" ? "取締件數" : "達成率"}</th>${items.map((item) => `<td class="performance-cell" tabindex="0">${kind === "rate" ? rate(item) : value(item, kind)}</td>`).join("")}</tr>`;
    const rows = data.rows.map((row) => `${triplet(row.unit, row.cells, "target")}${triplet("", row.cells, "actual")}${triplet("", row.cells, "rate")}`).join(""); const totalRow = (label, kind) => `<tr class="performance-${kind}"><th colspan="2">${label}</th>${columns.map((column) => { const item = totals[column.key] || { target: 0, actual: null, rate: null }; const text = kind === "actual" ? value(item, "actual") : kind === "target" ? value(item, "target") : kind === "difference" ? item.difference === null ? "—" : Number(item.difference).toLocaleString() : rate(item); return `<td class="performance-cell" tabindex="0">${text}</td>`; }).join("")}</tr>`;
    const period = $("majorPerformancePeriod").value === "week" ? "週" : "月"; $("majorPerformanceTable").innerHTML = `<p class="muted">目標來源：${esc(data.targetSource)}${data.statisticsSources?.length ? `；統計值來源：${data.statisticsSources.map(esc).join("、")}` : "；取締件數由重大違規原始資料計算"}。點選任一數值可標記為紅字。</p><table class="performance-table"><thead><tr><th colspan="2">項目</th>${columns.map((item) => `<th>${esc(item.label)}</th>`).join("")}</tr></thead><tbody>${rows}${totalRow("合計", "actual")}${totalRow(`${period}目標值`, "target")}${totalRow(`與${period}目標值差異`, "difference")}${totalRow("總達成率", "rate")}</tbody></table>`;
    $("majorPerformanceTable").querySelectorAll(".performance-cell").forEach((cell) => { cell.onclick = () => cell.classList.toggle("performance-marked"); cell.onkeydown = (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); cell.classList.toggle("performance-marked"); } }; });
  }
  async function loadTargets() { const button = $("majorTargetLoadButton"); button.disabled = true; try { const data = await targetRequest.json("/major-violation/performance-target", { method: "POST", headers: { "X-Performance-Token": state.performanceToken, "X-Performance-Period": $("majorPerformancePeriod").value }, body: upload("majorTargetFileInput", "target") }); state.performanceToken = data.token; $("majorTargetStatus").textContent = `已載入 ${data.sourceName}，共 ${data.units.length} 個單位。${(data.warnings || []).join(" ")}`; } catch (error) { if (!isAbort(error)) $("majorTargetStatus").textContent = error.message; } finally { button.disabled = false; } }
  async function loadStatistics() { const button = $("majorStatisticsLoadButton"); button.disabled = true; try { const data = await targetRequest.json("/major-violation/performance-statistics", { method: "POST", headers: { "X-Performance-Token": state.performanceToken }, body: upload("majorStatisticsFileInput", "statistics", true) }); state.performanceToken = data.token; state.majorStatisticKeys = data.availableKeys || []; renderChoices(state.majorStatisticKeys); $("majorStatisticsStatus").textContent = `已載入 ${data.sourceNames.join("、")}。可選 ${state.majorStatisticKeys.length} 個項目。${(data.warnings || []).join(" ")}`; } catch (error) { if (!isAbort(error)) $("majorStatisticsStatus").textContent = error.message; } finally { button.disabled = false; } }
  async function loadPerformance() { if (!state.performanceToken) { $("majorPerformanceStatus").textContent = "請先載入績效目標值與統計值。"; return; } try { $("majorPerformanceStatus").textContent = "正在計算週報績效…"; renderPerformance(await performanceRequest.json("/major-violation/performance", jsonOptions(performanceOptions()))); $("majorPerformanceStatus").textContent = "已依目標值與目前篩選資料完成計算。"; } catch (error) { if (!isAbort(error)) $("majorPerformanceStatus").textContent = error.message; } }
  function savePerformanceImage() {
    const table = $("majorPerformanceTable").querySelector("table");
    if (!table || !state.majorPerformance) { $("majorPerformanceStatus").textContent = "請先產生合計表。"; return; }
    const rows = Array.from(table.rows), scale = 2, width = Math.max(900, table.scrollWidth) * scale, height = (rows.length * 34 + 70) * scale;
    const canvas = document.createElement("canvas"); canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext("2d"), canvasWidth = width / scale, font = '"PingFang TC", "Microsoft JhengHei", sans-serif';
    ctx.scale(scale, scale); ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvasWidth, height / scale); ctx.font = `bold 18px ${font}`; ctx.fillStyle = "#17324d"; ctx.fillText("重大交通違規績效合計表", 12, 26);
    const yStart = 42, rowHeight = 34, colCount = rows[0].cells.length, colWidth = canvasWidth / colCount;
    rows.forEach((row, rowIndex) => Array.from(row.cells).forEach((cell, index) => { const x = index * colWidth, y = yStart + rowIndex * rowHeight; ctx.fillStyle = rowIndex === 0 ? "#e9f2fb" : row.className.includes("rate") ? "#f6f6f6" : "#fff"; ctx.fillRect(x, y, colWidth, rowHeight); ctx.strokeStyle = "#1f2937"; ctx.strokeRect(x, y, colWidth, rowHeight); ctx.fillStyle = cell.classList.contains("performance-marked") ? "#dc2626" : "#111"; ctx.font = `${rowIndex === 0 || cell.tagName === "TH" ? "bold " : ""}12px ${font}`; ctx.textAlign = "center"; ctx.fillText(cell.textContent.trim(), x + colWidth / 2, y + 22); }));
    const link = document.createElement("a"); link.download = "重大交通違規績效合計表.png"; link.href = canvas.toDataURL("image/png"); link.click();
  }
  async function clearData() {
    loadRequest.abort(); analysisRequest.abort(); if (state.majorToken) { try { await fetch("/clear", jsonOptions({ token: state.majorToken })); } catch (_) { /* local reset */ } }
    state.majorToken = ""; state.majorLatest = null; $("majorFileInput").value = ""; $("majorStartDate").value = ""; $("majorEndDate").value = ""; $("majorSources").innerHTML = ""; $("majorMetrics").innerHTML = ""; $("majorRule").textContent = ""; $("majorCategories").innerHTML = "<p>尚未載入資料</p>"; $("majorRankingTable").innerHTML = "<p>尚未載入資料</p>"; $("majorTrendTable").innerHTML = "<p>尚未載入資料</p>"; $("majorCategory").innerHTML = ""; chart.clear(); setStatus("已清除重大違規資料。");
  }
  async function clearPerformance() {
    targetRequest.abort(); performanceRequest.abort(); if (state.performanceToken) { try { await fetch("/clear", jsonOptions({ token: state.performanceToken })); } catch (_) { /* local reset */ } }
    state.performanceToken = ""; state.majorPerformance = null; state.majorStatisticKeys = []; $("majorTargetFileInput").value = ""; $("majorStatisticsFileInput").value = ""; $("majorPerformanceStartDate").value = ""; $("majorPerformanceEndDate").value = ""; $("majorTargetStatus").textContent = ""; $("majorStatisticsStatus").textContent = ""; $("majorPerformanceStatus").textContent = "已清除週報資料。"; $("majorPerformanceChoices").innerHTML = "<p>載入統計值後可選擇合計表項目。</p>"; $("majorPerformanceTable").innerHTML = "<p>請先載入績效目標值與統計值。</p>";
  }
  function showWorkspace(kind) { document.querySelectorAll(".major-workspace-data").forEach((item) => item.classList.toggle("hidden", kind !== "data")); document.querySelectorAll(".major-workspace-performance").forEach((item) => item.classList.toggle("hidden", kind !== "performance")); document.querySelectorAll("[data-major-workspace]").forEach((button) => button.classList.toggle("active", button.dataset.majorWorkspace === kind)); }
  function showPanel(kind) { document.querySelectorAll(".major-panel").forEach((item) => item.classList.toggle("hidden", item.id !== `major-panel-${kind}`)); document.querySelectorAll("[data-major-panel]").forEach((button) => button.classList.toggle("active", button.dataset.majorPanel === kind)); if (kind === "ranking") renderAnalysis(); }
  $("majorLoadButton").onclick = loadData; $("majorClearButton").onclick = clearData; $("majorAnalyzeButton").onclick = analyze; $("majorTargetLoadButton").onclick = loadTargets; $("majorStatisticsLoadButton").onclick = loadStatistics; $("majorPerformanceClearButton").onclick = clearPerformance; $("majorPerformanceButton").onclick = loadPerformance; $("majorPerformanceImageButton").onclick = savePerformanceImage; $("majorGroup").onchange = renderAnalysis; $("majorCategory").onchange = renderAnalysis; $("majorMetric").onchange = renderAnalysis; $("majorPeriod").onchange = analyze; $("majorTop").onchange = analyze; document.querySelectorAll("[data-major-panel]").forEach((button) => { button.onclick = () => showPanel(button.dataset.majorPanel); }); document.querySelectorAll("[data-major-workspace]").forEach((button) => { button.onclick = () => showWorkspace(button.dataset.majorWorkspace); });
}

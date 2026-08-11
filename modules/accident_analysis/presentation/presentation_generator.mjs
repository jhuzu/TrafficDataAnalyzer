import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";
import sharp from "sharp";

const args = {};
for (let i = 2; i < process.argv.length; i += 1) {
  if (process.argv[i].startsWith("--")) args[process.argv[i].slice(2)] = process.argv[i + 1] ?? "";
}

const inputPath = path.resolve(args.data || "");
const templatePath = path.resolve(args.template || "");
const outputPath = path.resolve(args.output || "");
if (!inputPath || !templatePath || !outputPath) throw new Error("需要 --data、--template、--output。");

const source = JSON.parse(await fs.readFile(inputPath, "utf8"));
const headers = source.headers || [];
const sourceRows = source.rows || [];
const idx = Object.fromEntries(headers.map((name, i) => [name, i]));
const value = (row, field) => {
  const raw = field in idx ? row[idx[field]] : "";
  return raw === null || raw === undefined ? "" : String(raw).trim();
};
const count = row => Number(value(row, "件數")) || 0;
const a1a2Rows = sourceRows.filter(row => ["A1", "A2"].includes(value(row, "事故類別").toUpperCase()));
const rows = a1a2Rows.length ? a1a2Rows : sourceRows;
const fmt = n => Math.round(Number(n) || 0).toLocaleString("zh-TW");
const pct = (n, total) => total ? `${(n * 100 / total).toFixed(1)}%` : "0.0%";
const group = (sourceRows, field, limit = 10, transform = v => v) => {
  const totals = new Map();
  for (const row of sourceRows) {
    const raw = transform(value(row, field), row);
    if (!raw) continue;
    totals.set(raw, (totals.get(raw) || 0) + count(row));
  }
  return [...totals.entries()]
    .map(([label, amount]) => ({ label, count: amount }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "zh-Hant"))
    .slice(0, limit);
};
const ageNumber = row => {
  const n = Number(value(row, "年齡").replace(/歲/g, ""));
  return Number.isFinite(n) ? n : null;
};
const ageGroups = [
  ["18-30歲", 18, 30], ["31-40歲", 31, 40], ["41-50歲", 41, 50],
  ["51-60歲", 51, 60], ["61-70歲", 61, 70],
].map(([label, lo, hi]) => ({ label, count: rows.reduce((sum, row) => {
  const age = ageNumber(row); return age !== null && age >= lo && age <= hi ? sum + count(row) : sum;
}, 0) }));

const total = rows.reduce((s, row) => s + count(row), 0);
const a1Rows = rows.filter(row => value(row, "事故類別").toUpperCase() === "A1");
const a2Rows = rows.filter(row => value(row, "事故類別").toUpperCase() === "A2");
const a1Total = a1Rows.reduce((s, row) => s + count(row), 0);
const a2Total = a2Rows.reduce((s, row) => s + count(row), 0);
const roads = group(rows, "路段");
const intersections = group(rows, "路段", 10, (road, row) => {
  const cross = value(row, "交叉路名"); return road && cross ? `${road}／${cross}` : "";
});
const causes = group(rows, "肇事原因", 6);
const vehicles = group(rows, "當事者區分", 10);
const timeGroups = group(rows, "發生時間", 7, raw => {
  const n = Number(raw.slice(0, 2)); return Number.isFinite(n) ? `${String(Math.floor(n / 2) * 2).padStart(2, "0")} - ${String(Math.floor(n / 2) * 2 + 2).padStart(2, "0")} 時` : "時間不詳";
});
const topVehicle = vehicles[0] || { label: "未提供", count: 0 };
const secondVehicle = vehicles[1] || { label: "未提供", count: 0 };
const period = args.period || "115年1月1日至8月31日";
const periodShort = period.replace(/^(.+?年)(\d+)月\d+日至(\d+)月\d+日$/, "$1$2-$3月");

function incidentTime(row) {
  return `${value(row, "發生月")}月${value(row, "發生日")}日 ${value(row, "發生時間")}`.replace(/月日/, "月");
}
function incidentLocation(row) {
  return [value(row, "路段"), value(row, "交叉路名")].filter(Boolean).join("／") || value(row, "其他地點") || "未提供";
}
const fatalRows = a1Rows.slice(0, 7).map((row, i) => [
  String(i + 1), incidentTime(row), incidentLocation(row), value(row, "肇事原因") || "未提供",
  value(row, "當事者區分") || "未提供", `${value(row, "死亡人數") || "1"}人死亡`,
]);
while (fatalRows.length < 7) fatalRows.push([String(fatalRows.length + 1), "", "", "", "", ""]);

const summary = `本期統計${fmt(total)}件；易肇事路段以${roads[0]?.label || "未提供"}（${fmt(roads[0]?.count || 0)}件）為首，主要肇因為${causes[0]?.label || "未提供"}（${fmt(causes[0]?.count || 0)}件），應依熱點與高風險時段持續部署勤務。`;
const enforcement = `建議以${roads[0]?.label || "主要熱點路段"}及${timeGroups[0]?.label || "高峰時段"}列為優先勤務區段，針對${causes[0]?.label || "主要肇因"}加強宣導、攔查及違規取締。`;

const presentation = await PresentationFile.importPptx(await FileBlob.load(templatePath));
const originals = [...(presentation.slides.items || [])];
const copies = originals.map(slide => slide.duplicate());
for (const slide of originals) slide.delete();
copies.forEach((slide, i) => slide.moveTo(i));

const snapshot = await presentation.inspect({ kind: "textbox,table", include: "id,slide,name,text,textPreview,bbox,rows,cols", maxChars: 200000 });
const objects = (snapshot.ndjson || "").split("\n").filter(Boolean).map(line => JSON.parse(line));
const find = (kind, slide, name) => {
  const hit = objects.find(item => item.kind === kind && item.slide === slide && item.name === name);
  return hit ? presentation.resolve(hit.id) : null;
};
const setText = (slide, name, text) => { const box = find("textbox", slide, name); if (box) box.text = text; };
const setTable = (slide, name, matrix) => {
  const table = find("table", slide, name); if (!table) return;
  const rowsCount = table.rows?.length || matrix.length;
  const colsCount = matrix[0]?.length || 0;
  for (let r = 0; r < rowsCount; r += 1) for (let c = 0; c < colsCount; c += 1) table.cells.set(r, c, matrix[r]?.[c] ?? "");
};
const findImage = (slide, name) => {
  const hit = objects.find(item => item.kind === "image" && item.slide === slide && item.name === name);
  return hit ? presentation.resolve(hit.id) : null;
};

// The skeleton stores the time bars as seven separate raster layers. Repaint
// those layers from the current data while preserving each layer's frame.
const makeTimeBarPng = async (amount, maximum, index) => {
  const width = 444;
  const height = 18;
  const ratio = maximum > 0 ? Math.max(0, Math.min(1, amount / maximum)) : 0;
  const barWidth = Math.max(0, Math.round(width * ratio));
  const start = index < 3 ? "#ff7417" : "#2f76e6";
  const end = index < 3 ? "#ef4444" : "#1f56b2";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
    <defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="${start}"/><stop offset="1" stop-color="${end}"/></linearGradient></defs>
    <rect x="0" y="0" width="${barWidth}" height="${height}" rx="9" fill="url(#g)"/>
  </svg>`;
  return sharp(Buffer.from(svg)).png().toBuffer();
};
const makeTimeTrackPng = async () => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="444" height="18">
    <rect x="0" y="0" width="444" height="18" rx="9" fill="#dfe6ef"/>
  </svg>`;
  return sharp(Buffer.from(svg)).png().toBuffer();
};
const makeTimePanelPng = async () => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="578" height="528">
    <rect x="0.5" y="0.5" width="577" height="527" rx="14" fill="#f8fafc" stroke="#d7e0ea"/>
    <line x1="20" y1="56" x2="558" y2="56" stroke="#d7e0ea" stroke-width="1"/>
    <rect x="13" y="458" width="544" height="56" rx="12" fill="#fff0e3" stroke="#f3cda8"/>
  </svg>`;
  return sharp(Buffer.from(svg)).png().toBuffer();
};
const artifactBytes = buffer => buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);

setText(1, "TextBox 13", period);
setText(2, "TextBox 13", periodShort);
setText(2, "TextBox 17", `A1+A2 事故總件數\n${fmt(total)} 件`);
setText(2, "文字方塊 3", `${fmt(total)}件`);
setText(2, "TextBox 18", `較前期變化：${fmt(total)} 件`);
setText(2, "TextBox 20", `${fmt(a1Total)} 件`);
setText(2, "TextBox 21", `占總數 ${pct(a1Total, total)}`);
setText(2, "TextBox 23", `${fmt(a2Total)} 件`);
setText(2, "TextBox 24", `占總數 ${pct(a2Total, total)}`);
setText(2, "TextBox 27", `整體狀況：${summary}`);
setText(2, "TextBox 29", `核心防制重點：${causes[0]?.label || "主要肇因"}及${topVehicle.label}為本期優先關注項目。`);
setText(2, "TextBox 31", `防制方向：針對${roads[0]?.label || "易肇事路段"}、${timeGroups[0]?.label || "高風險時段"}及主要肇因加強執法。`);

setTable(3, "Table 15", [["排名", "路段名稱", "發生件數"], ...Array.from({ length: 10 }, (_, i) => [String(i + 1), roads[i]?.label || "", roads[i] ? `${fmt(roads[i].count)} 件` : ""]) ]);
setTable(4, "Table 15", [["排名", "路口名稱", "件數"], ...Array.from({ length: 10 }, (_, i) => [String(i + 1), intersections[i]?.label || "", intersections[i] ? `${fmt(intersections[i].count)} 件` : ""]) ]);
setTable(5, "Table 33", [["排名", "肇事原因", "件數 (占比)"], ...Array.from({ length: 6 }, (_, i) => [String(i + 1), causes[i]?.label || "", causes[i] ? `${fmt(causes[i].count)}件 (${pct(causes[i].count, total)})` : ""]) ]);
for (const [name, item] of ["TextBox 37", "TextBox 38", "TextBox 39", "TextBox 40", "TextBox 41", "TextBox 42", "TextBox 43"].map((name, i) => [name, timeGroups[i]])) setText(5, name, item ? `${item.label}` : "");
for (const [name, item] of [["TextBox 62", timeGroups[0]], ["TextBox 63", timeGroups[1]], ["TextBox 64", timeGroups[2]]]) setText(5, name, item ? `${fmt(item.count)}件 (${pct(item.count, total)})` : "");
const maxTimeCount = Math.max(0, ...timeGroups.map(item => item.count));
const slide5 = presentation.slides.items?.[4];
const timePanel = findImage(5, "Picture 4");
const panelPng = await makeTimePanelPng();
// Add clean layers above the flattened source art. This is intentional: the
// imported skeleton's chart is flattened into a full-panel image, so a new
// panel layer is more reliable than trying to mutate its internal pixels.
if (slide5) slide5.images.add({
  blob: artifactBytes(panelPng), contentType: "image/png", alt: "事故時段圖表背景",
  fit: "contain", position: { left: 50, top: 122, width: 578, height: 528 },
});
const trackPng = await makeTimeTrackPng();
for (let i = 0; i < 7; i += 1) {
  if (slide5) slide5.images.add({
    blob: artifactBytes(trackPng), contentType: "image/png", alt: `事故時段${i + 1}背景軌道`,
    fit: "contain", position: { left: 163, top: 188 + i * 26, width: 444, height: 18 },
  });
  const png = await makeTimeBarPng(timeGroups[i]?.count || 0, maxTimeCount, i);
  if (slide5) slide5.images.add({
    blob: artifactBytes(png), contentType: "image/png", alt: `事故時段${i + 1}自動重繪圖`,
    fit: "contain", position: { left: 163, top: 188 + i * 26, width: 444, height: 18 },
  });
}
const addOverlayText = (text, position, style = {}) => {
  if (!slide5) return;
  const box = slide5.shapes.add({ geometry: "textbox", position, fill: "none", line: { style: "solid", fill: "none", width: 0 } });
  box.text = text;
  box.text.style = { fontSize: 12, color: "#26364a", ...style };
  return box;
};
addOverlayText("事故發生時段分布 (2小時區間)", { left: 93, top: 143, width: 514, height: 25 }, { fontSize: 19, bold: true, color: "#21438c" });
for (let i = 0; i < 7; i += 1) {
  const item = timeGroups[i];
  addOverlayText(item?.label || "", { left: 71, top: 188 + i * 26, width: 80, height: 18 }, { fontSize: 12, bold: true });
  if (item) {
    const ratio = maxTimeCount ? item.count / maxTimeCount : 0;
    const labelWidth = 115;
    const labelLeft = 163 + Math.max(5, Math.round(444 * ratio) - labelWidth - 4);
    addOverlayText(`${fmt(item.count)}件 (${pct(item.count, total)})`, { left: labelLeft, top: 188 + i * 26, width: labelWidth, height: 18 }, { fontSize: 11, bold: true, color: "#ffffff", align: "right" });
  }
}
addOverlayText("尖峰時段結論：", { left: 68, top: 580.66, width: 500, height: 26 }, { fontSize: 15, bold: true });
for (const name of ["TextBox 27", "TextBox 37", "TextBox 38", "TextBox 39", "TextBox 40", "TextBox 41", "TextBox 42", "TextBox 43", "TextBox 62", "TextBox 63", "TextBox 64", "文字方塊 2"]) {
  const box = find("textbox", 5, name);
  if (box?.bringToFront) box.bringToFront();
}
const clock = findImage(5, "Picture 35");
if (clock?.bringToFront) clock.bringToFront();

const ageRows = ageGroups.map((item, i) => [item.label, `${fmt(item.count)} 件`, pct(item.count, total), i === 0 ? "最高極危" : i < 3 ? "高" : "中"]);
setTable(6, "Table 17", [["年齡區間", "件數", "占比", "風險等級"], ...ageRows.slice(0, 5)]);
const vehicleRows = ["其他車種", "慢車(含微電車)", "小貨車", "大貨車/客車"].map(label => {
  const found = vehicles.find(item => item.label.includes(label.replace("(含微電車)", "")) || item.label.includes(label.split("(")[0]));
  return found ? `${fmt(found.count)} 件 (${pct(found.count, total)})` : "0 件";
});
setTable(6, "Table 21", [["其他車種", "慢車(含微電車)", "小貨車", "大貨車/客車"], vehicleRows]);
setText(6, "TextBox 47", `${fmt(topVehicle.count)} 件`);
setText(6, "TextBox 48", `占比 ${pct(topVehicle.count, total)}`);
setText(6, "TextBox 51", `${fmt(secondVehicle.count)} 件`);
setText(6, "TextBox 52", `占比 ${pct(secondVehicle.count, total)}`);

setTable(7, "Table 11", [["編號", "發生時間", "發生地點", "肇因研判", "車種別", "死亡類別 / 備註"], ...fatalRows]);
setText(7, "TextBox 12", `A1案件防制結論：本期A1事故共${fmt(a1Total)}件，應針對${fatalRows[0]?.[2] || "事故熱點"}及行人、機車等高風險樣態列入追蹤。`);
setText(8, "TextBox 20", `專案日程：${period}`);
setText(8, "TextBox 27", `熱點編排：${enforcement}`);
setText(8, "TextBox 29", `A1路段重點執法：針對${roads[0]?.label || "首要熱點"}及${timeGroups[0]?.label || "高風險時段"}安排勤務，並依週報件數滾動檢討。`);
setText(8, "TextBox 30", `嘉獎核予標準：專案期間每執行超速取締勤務達${Math.max(1, Math.round((total || 0) / 200))}小時，且總取締件數不低於${Math.max(1, Math.round((total || 0) / 20))}件者，核予嘉獎一次。`);

for (const slide of copies) {
  slide.speakerNotes.textFrame.setText(`[Sources]\n- Data: loaded Excel Pivot Cache session (件數欄加總)\n- Template: 事故分析模組骨架模板\n[/Sources]`);
  slide.speakerNotes.setVisible(true);
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await PresentationFile.exportPptx(presentation);
await output.save(outputPath);
console.log(JSON.stringify({ output: outputPath, slides: copies.length, total, a1Total, a2Total }));

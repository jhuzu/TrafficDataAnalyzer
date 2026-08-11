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
if (!args.data || !args.template || !args.output) throw new Error("需要 --data、--template、--output。");

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
if (payload.schemaVersion !== "accident-weekly-report/v1") {
  throw new Error(`不支援的簡報資料格式：${payload.schemaVersion || "未提供版本"}`);
}
const fmt = number => Math.round(Number(number) || 0).toLocaleString("zh-TW");
const pct = (number, total) => total ? `${(number * 100 / total).toFixed(1)}%` : "0.0%";
const escapeXml = text => String(text ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&apos;");
const shortLabel = (text, max = 13) => {
  const string = String(text ?? "");
  return string.length > max ? `${string.slice(0, max - 1)}…` : string;
};

const overview = payload.overview || {};
const rankings = payload.rankings || {};
const distributions = payload.distributions || {};
const total = Number(overview.total) || 0;
const a1Total = Number(overview.a1) || 0;
const a2Total = Number(overview.a2) || 0;
const roads = (rankings.roads || []).slice(0, 10);
const roadCount = Number(overview.roadCategoryCount) || 0;
const intersections = (rankings.intersections || []).slice(0, 10);
const causes = (rankings.causes || []).slice(0, 12);
const vehicles = (rankings.vehicles || []).slice(0, 7);
const a1Roads = (rankings.a1Roads || []).slice(0, 2);
const ageGroups = (distributions.ageGroups || []).slice(0, 7);
const timeGroups = (distributions.timeBuckets || []).slice(0, 12);
const rankedTimes = (distributions.rankedTimeBuckets || []).slice(0, 12);
const period = payload.period?.display || "115年1月1日至8月31日";
const year = payload.period?.year || "";
const fatalRows = (payload.a1Details || []).slice(0, 7).map(item => [
  String(item.number), item.time, item.location, item.cause, item.vehicle,
  `${item.deaths || "1"}人`, item.notes || "",
]);
while (fatalRows.length < 7) fatalRows.push([String(fatalRows.length + 1), "", "", "", "", "", ""]);

const summary = payload.narrative?.summary || "本期無可用事故摘要。";

const presentation = await PresentationFile.importPptx(await FileBlob.load(templatePath));
const originals = [...(presentation.slides.items || [])];
const copies = originals.map(slide => slide.duplicate());
for (const slide of originals) slide.delete();
copies.forEach((slide, index) => slide.moveTo(index));

const snapshot = await presentation.inspect({
  kind: "textbox,table",
  include: "id,slide,name,text,textPreview,bbox,rows,cols",
  maxChars: 300000,
});
const objects = (snapshot.ndjson || "").split("\n").filter(Boolean).map(line => JSON.parse(line));
const record = (slide, name) => objects.find(item => item.slide === slide && item.name === name);
const resolve = (slide, name) => {
  const item = record(slide, name);
  return item ? presentation.resolve(item.id) : null;
};
const setText = (slide, name, text) => {
  const target = resolve(slide, name);
  if (target) target.text = text;
};
const setTable = (slide, name, matrix) => {
  const target = resolve(slide, name);
  if (!target) return;
  for (let row = 0; row < matrix.length; row += 1) {
    for (let column = 0; column < matrix[row].length; column += 1) {
      target.cells.set(row, column, matrix[row][column] ?? "");
    }
  }
};
const artifactBytes = buffer => buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);

async function horizontalChart(items, width, height, color = "#2F75B5") {
  const safeItems = items.length ? items : [{ label: "無資料", count: 0 }];
  const maximum = Math.max(1, ...safeItems.map(item => item.count));
  const margin = 12;
  const labelWidth = Math.round(width * 0.35);
  const plotWidth = width - labelWidth - 54;
  const rowHeight = (height - margin * 2) / safeItems.length;
  const bars = safeItems.map((item, index) => {
    const y = margin + index * rowHeight;
    const barHeight = Math.max(5, rowHeight * 0.55);
    const barWidth = Math.max(item.count ? 2 : 0, plotWidth * item.count / maximum);
    return `<text x="${margin}" y="${y + barHeight}" font-size="${Math.min(13, Math.max(8, rowHeight * 0.45))}" fill="#26364A">${escapeXml(shortLabel(item.label))}</text>
      <rect x="${labelWidth}" y="${y}" width="${barWidth}" height="${barHeight}" rx="3" fill="${color}"/>
      <text x="${Math.min(width - 8, labelWidth + barWidth + 5)}" y="${y + barHeight}" font-size="${Math.min(12, Math.max(8, rowHeight * 0.42))}" fill="#26364A">${fmt(item.count)}</text>`;
  }).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="#FFFFFF"/>${bars}</svg>`;
  return sharp(Buffer.from(svg)).png().toBuffer();
}

async function verticalChart(items, width, height, colors = ["#2F75B5"]) {
  const safeItems = items.length ? items : [{ label: "無資料", count: 0 }];
  const maximum = Math.max(1, ...safeItems.map(item => item.count));
  const margin = { left: 28, right: 10, top: 22, bottom: 30 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const step = plotWidth / safeItems.length;
  const barWidth = Math.max(5, step * 0.58);
  const bars = safeItems.map((item, index) => {
    const barHeight = plotHeight * item.count / maximum;
    const x = margin.left + index * step + (step - barWidth) / 2;
    const y = margin.top + plotHeight - barHeight;
    const color = colors[index % colors.length];
    return `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="2" fill="${color}"/>
      <text x="${x + barWidth / 2}" y="${Math.max(11, y - 3)}" text-anchor="middle" font-size="10" fill="#26364A">${fmt(item.count)}</text>
      <text x="${x + barWidth / 2}" y="${height - 9}" text-anchor="middle" font-size="9" fill="#26364A">${escapeXml(shortLabel(item.label, 7))}</text>`;
  }).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="#FFFFFF"/><line x1="${margin.left}" y1="${margin.top + plotHeight}" x2="${width - margin.right}" y2="${margin.top + plotHeight}" stroke="#C9D2DC"/>${bars}</svg>`;
  return sharp(Buffer.from(svg)).png().toBuffer();
}

async function replaceChart(slideNumber, name, imageBuffer, alt) {
  const item = record(slideNumber, name);
  const target = resolve(slideNumber, name);
  if (!item?.bbox || !target) throw new Error(`模板缺少圖表預留區：第${slideNumber}頁 ${name}`);
  target.delete();
  const [left, top, width, height] = item.bbox;
  const slide = presentation.slides.items?.[slideNumber - 1];
  slide.images.add({
    blob: artifactBytes(imageBuffer), contentType: "image/png", alt,
    fit: "contain", position: { left, top, width, height },
  });
}

setText(1, "矩形 14", `${period}\nA1+A2：${fmt(total)}件（${overview.changes?.total?.text || "未提供同期資料"}）\nA1：${fmt(a1Total)}件（${overview.changes?.a1?.text || "未提供同期資料"}）\nA2：${fmt(a2Total)}件（${overview.changes?.a2?.text || "未提供同期資料"}）\n\n${summary}`);
setText(2, "矩形 38", `路段：${shortLabel(roads[0]?.label || "未提供", 12)} ${fmt(roads[0]?.count || 0)}件；${shortLabel(roads[1]?.label || "未提供", 12)} ${fmt(roads[1]?.count || 0)}件；${shortLabel(roads[2]?.label || "未提供", 12)} ${fmt(roads[2]?.count || 0)}件。共${fmt(roadCount)}處。`);
setTable(2, "表格 7", [["排名", ...roads.map(item => item.label), ...Array(10 - roads.length).fill("")], ["件數", ...roads.map(item => fmt(item.count)), ...Array(10 - roads.length).fill("")], ["排名", ...Array.from({ length: 10 }, (_, index) => String(index + 1))]]);
setText(3, "矩形 24", `事故路口以${shortLabel(intersections[0]?.label || "未提供", 16)}發生${fmt(intersections[0]?.count || 0)}件最多。`);
const intersectionSummary = resolve(3, "矩形 24");
if (intersectionSummary) {
  intersectionSummary.position = { left: 486.92, top: 525, width: 465.78, height: 58 };
  intersectionSummary.text.style = { fontSize: 14, bold: true, color: "#0000FF" };
}
setTable(3, "表格 23", [["排名", ...intersections.map(item => item.label), ...Array(10 - intersections.length).fill("")], ["件數", ...intersections.map(item => fmt(item.count)), ...Array(10 - intersections.length).fill("")], ["排名", ...Array.from({ length: 10 }, (_, index) => String(index + 1))]]);
setText(4, "矩形 21", `肇因：${causes[0]?.label || "未提供"} ${fmt(causes[0]?.count || 0)}件（${pct(causes[0]?.count || 0, total)}）；${causes[1]?.label || "未提供"} ${fmt(causes[1]?.count || 0)}件（${pct(causes[1]?.count || 0, total)}）；${causes[2]?.label || "未提供"} ${fmt(causes[2]?.count || 0)}件（${pct(causes[2]?.count || 0, total)}）。`);
setText(4, "矩形 27", `時段：${rankedTimes[0]?.label || "未提供"}時 ${fmt(rankedTimes[0]?.count || 0)}件（${pct(rankedTimes[0]?.count || 0, total)}）；${rankedTimes[1]?.label || "未提供"}時 ${fmt(rankedTimes[1]?.count || 0)}件（${pct(rankedTimes[1]?.count || 0, total)}）；${rankedTimes[2]?.label || "未提供"}時 ${fmt(rankedTimes[2]?.count || 0)}件（${pct(rankedTimes[2]?.count || 0, total)}）。`);
setTable(4, "表格 26", [["時間", ...timeGroups.map(item => item.label)], ["件數", ...timeGroups.map(item => fmt(item.count))]]);
setTable(4, "表格 29", [["排名", ...Array.from({ length: 12 }, (_, index) => String(index + 1))], ["肇因", ...causes.map(item => item.label), ...Array(12 - causes.length).fill("")], ["件數", ...causes.map(item => fmt(item.count)), ...Array(12 - causes.length).fill("")]]);
setText(5, "矩形 19", `年齡：${ageGroups[0]?.label || "未提供"} ${fmt(ageGroups[0]?.count || 0)}件（${pct(ageGroups[0]?.count || 0, total)}）；${ageGroups[1]?.label || "未提供"} ${fmt(ageGroups[1]?.count || 0)}件（${pct(ageGroups[1]?.count || 0, total)}）；${ageGroups[2]?.label || "未提供"} ${fmt(ageGroups[2]?.count || 0)}件（${pct(ageGroups[2]?.count || 0, total)}）。`);
setText(5, "矩形 26", `車種：${vehicles[0]?.label || "未提供"} ${fmt(vehicles[0]?.count || 0)}件（${pct(vehicles[0]?.count || 0, total)}）；${vehicles[1]?.label || "未提供"} ${fmt(vehicles[1]?.count || 0)}件（${pct(vehicles[1]?.count || 0, total)}）；${vehicles[2]?.label || "未提供"} ${fmt(vehicles[2]?.count || 0)}件（${pct(vehicles[2]?.count || 0, total)}）。`);
setTable(5, "表格 18", [["年齡", ...ageGroups.map(item => item.label)], ["件數", ...ageGroups.map(item => fmt(item.count))]]);
setTable(5, "表格 25", [["車種", ...vehicles.map(item => item.label), ...Array(7 - vehicles.length).fill("")], ["件數", ...vehicles.map(item => fmt(item.count)), ...Array(7 - vehicles.length).fill("")]]);
setTable(6, "表格 12", [[`板橋分局轄內${year}年度A1事故明細`, "", "", "", "", "", ""], ["編號", "時間", "地點", "肇因", "車種", "死亡", "備註"], ...fatalRows]);
const primaryA1Road = a1Roads[0]?.label || roads[0]?.label || "未提供";
const secondaryA1Road = a1Roads[1]?.label || roads.find(item => item.label !== primaryA1Road)?.label || "未提供";
setText(7, "文字方塊 3", `一、日程：${period}\n\n二、勤務方式：\n　（一）各所、隊於${roads[0]?.label || "主要事故熱點"}編排勤務，加強取締超速。\n\n　（二）加強取締A1事故路段：${primaryA1Road}、${secondaryA1Road}。\n\n四、獎勵規定：每執行超速取締勤務達${Math.max(1, Math.round(total / 200))}小時，且總取締件數不低於${Math.max(1, Math.round(total / 20))}件者，核予嘉獎一次，以嘉獎3次為上限。`);

await replaceChart(1, "程式圖表預留區-1-圖表 26", await verticalChart([{ label: "A1", count: a1Total }, { label: "A2", count: a2Total }], 860, 670, ["#C00000", "#ED7D31"]), "A1與A2事故件數比較圖");
await replaceChart(2, "程式圖表預留區-2-圖表 19", await horizontalChart(roads, 854, 464), "十大易肇事路段排行圖");
await replaceChart(3, "程式圖表預留區-3-圖表 20", await horizontalChart(intersections, 910, 470, "#ED7D31"), "十大易肇事路口排行圖");
await replaceChart(4, "程式圖表預留區-4-圖表 28", await horizontalChart(causes.slice(0, 8), 894, 438, "#5B9BD5"), "主要事故肇因排行圖");
await replaceChart(4, "程式圖表預留區-4-圖表 25", await verticalChart(timeGroups, 816, 404, ["#70AD47", "#5B9BD5", "#ED7D31"]), "事故發生時段分布圖");
await replaceChart(5, "程式圖表預留區-5-圖表 17", await horizontalChart(ageGroups, 840, 514, "#4472C4"), "事故年齡分布圖");
await replaceChart(5, "程式圖表預留區-5-圖表 24", await horizontalChart(vehicles, 806, 498, "#ED7D31"), "事故車種分布圖");

for (const slide of copies) {
  slide.speakerNotes.textFrame.setText(`[Sources]\n- Data: loaded Excel source (${payload.source?.sourceType || "unknown"}; 件數欄加總)\n- Template: 交通事故分析原版樣式自動填值模板\n- Summary and charts: shared deterministic offline payload ${payload.schemaVersion}; no external AI or network service\n[/Sources]`);
  slide.speakerNotes.setVisible(true);
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await PresentationFile.exportPptx(presentation);
await output.save(outputPath);
console.log(JSON.stringify({ output: outputPath, slides: copies.length, variant: "traditional", total, a1Total, a2Total }));

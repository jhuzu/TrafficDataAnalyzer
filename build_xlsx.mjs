import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [jsonPath, outputPath] = process.argv.slice(2);
if (!jsonPath || !outputPath) throw new Error("缺少輸入或輸出路徑。");
const { headers, rows } = JSON.parse(await fs.readFile(jsonPath, "utf8"));
const required = ["路段", "交叉路名", "發生時間", "肇事原因", "年齡", "當事者區分", "件數"];
const lastRow = rows.length + 1;
const missing = required.filter(name => !headers.includes(name));
if (missing.length) throw new Error(`Pivot Cache 缺少必要欄位：${missing.join("、")}`);

const toColumn = n => { let s = ""; for (n += 1; n; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s; return s; };
const field = Object.fromEntries(headers.map((h, i) => [h, toColumn(i)]));
const index = Object.fromEntries(headers.map((h, i) => [h, i]));
const count = row => Number(row[index["件數"]] || 0);
function topGroups(valueFn, max = 20) {
  const values = new Map();
  for (const row of rows) {
    const value = valueFn(row);
    if (value !== null && value !== undefined && String(value).trim() !== "") values.set(String(value), (values.get(String(value)) || 0) + count(row));
  }
  return [...values.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-Hant")).slice(0, max).map(([value]) => value);
}
const roads = topGroups(r => r[index["路段"]]);
const intersections = topGroups(r => r[index["路段"]] && r[index["交叉路名"]] ? `${r[index["路段"]]}／${r[index["交叉路名"]]}` : null);
const periods = topGroups(r => r[index["發生時間"]], 24);
const causes = topGroups(r => r[index["肇事原因"]]);
const vehicles = topGroups(r => r[index["當事者區分"]]);

const wb = Workbook.create();
const source = wb.worksheets.add("原始資料");
source.showGridLines = false;
source.getRange("A1:BX1").values = [[...headers, "路口"]];
source.getRange(`A2:${toColumn(headers.length - 1)}${rows.length + 1}`).values = rows;
source.getRange("BX2").formulas = [[`=IF(AND($${field["路段"]}2<>\"\",$${field["交叉路名"]}2<>\"\"),$${field["路段"]}2&\"／\"&$${field["交叉路名"]}2,\"\")`]];
source.getRange(`BX2:BX${lastRow}`).fillDown();
const table = source.tables.add(`A1:BX${rows.length + 1}`, true, "RecoveredPivotData");
table.style = "TableStyleMedium2";
table.showFilterButton = true;
source.getRange("A1:BX1").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
source.getRange("A:BX").format.columnWidth = 15;
source.getRange(`${field["路段"]}:${field["路段"]}`).format.columnWidth = 22;
source.getRange(`${field["肇事原因"]}:${field["肇事原因"]}`).format.columnWidth = 34;
source.freezePanes.freezeRows(1);

const sheet = wb.worksheets.add("分析表");
sheet.showGridLines = false;
sheet.mergeCells("A1:H1");
sheet.getRange("A1").values = [["交通事故統計分析"]];
sheet.getRange("A1:H1").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF", size: 14 }, horizontalAlignment: "center" };
sheet.getRange("A1:H1").format.rowHeight = 28;
sheet.mergeCells("A2:H2");
sheet.getRange("A2").values = [["本表由樞紐快取自動還原；藍底數量為公式加總。"]];
sheet.getRange("A2:H2").format = { font: { italic: true, color: "#4B5563", size: 10 } };

function header(left, right, row, title) {
  sheet.getRange(`${left}${row}:${right}${row}`).values = [[title, "數量"]];
  sheet.getRange(`${left}${row}:${right}${row}`).format = { fill: "#D9EAF7", font: { bold: true } };
  sheet.getRange(`${left}${row + 1}`).values = [["依輸入資料自動加總"]];
  sheet.getRange(`${left}${row + 1}`).format = { font: { italic: true, color: "#4B5563", size: 10 } };
}
function section(left, right, title, labels, sourceColumn, startRow, totalRow) {
  header(left, right, startRow - 2, title);
  sheet.getRange(`${left}${startRow}:${left}${startRow + labels.length - 1}`).values = labels.map(v => [v]);
  sheet.getRange(`${right}${startRow}:${right}${startRow + labels.length - 1}`).formulas = labels.map((_, i) => [`=SUMIF('原始資料'!$${sourceColumn}$2:$${sourceColumn}$${lastRow},${left}${startRow + i},'原始資料'!$${field["件數"]}$2:$${field["件數"]}$${lastRow})`]);
  sheet.getRange(`${left}${startRow}:${right}${startRow + labels.length - 1}`).format.borders = { preset: "insideHorizontal", style: "thin", color: "#D9E2F3" };
  sheet.getRange(`${right}${startRow}:${right}${startRow + labels.length - 1}`).format = { fill: "#DDEBF7", numberFormat: "#,##0" };
  sheet.getRange(`${left}${totalRow}`).values = [[`${title}合計`]];
  sheet.getRange(`${right}${totalRow}`).formulas = [[`=SUM('原始資料'!$${field["件數"]}$2:$${field["件數"]}$${lastRow})`]];
  sheet.getRange(`${left}${totalRow}:${right}${totalRow}`).format = { fill: "#D9EAF7", font: { bold: true }, numberFormat: "#,##0", borders: { preset: "doubleBottom", style: "thin", color: "#7F8C8D" } };
}

section("A", "B", "易肇事路段", roads, field["路段"], 6, 27);
header("D", "E", 4, "易肇事路口");
sheet.getRange("D6:D25").values = intersections.map(v => [v]);
sheet.getRange("E6:E25").formulas = intersections.map((_, i) => [`=SUMIF('原始資料'!$BX$2:$BX$${lastRow},D${6 + i},'原始資料'!$${field["件數"]}$2:$${field["件數"]}$${lastRow})`]);
sheet.getRange("D6:E25").format.borders = { preset: "insideHorizontal", style: "thin", color: "#D9E2F3" };
sheet.getRange("E6:E25").format = { fill: "#DDEBF7", numberFormat: "#,##0" };
sheet.getRange("D27:E27").values = [["易肇事路口合計", null]];
sheet.getRange("E27").formulas = [[`=COUNTIFS('原始資料'!$${field["路段"]}$2:$${field["路段"]}$${lastRow},\"<>\",'原始資料'!$${field["交叉路名"]}$2:$${field["交叉路名"]}$${lastRow},\"<>\")`]];
sheet.getRange("D27:E27").format = { fill: "#D9EAF7", font: { bold: true }, numberFormat: "#,##0", borders: { preset: "doubleBottom", style: "thin", color: "#7F8C8D" } };
section("G", "H", "易肇事時段", periods, field["發生時間"], 6, 31);
section("A", "B", "易肇事肇因", causes, field["肇事原因"], 43, 64);

header("D", "E", 41, "易肇事年齡");
sheet.getRange("D42:D51").values = [["0-17"],["18-20"],["21-30"],["31-40"],["41-50"],["51-60"],["61-70"],["71歲以上"],["沒有年紀"],["合計"]];
const intervals = [[0,17],[18,20],[21,30],[31,40],[41,50],[51,60],[61,70]];
const ageFx = intervals.map(([lo, hi]) => `=SUMIFS('原始資料'!$${field["件數"]}$2:$${field["件數"]}$${lastRow},'原始資料'!$${field["年齡"]}$2:$${field["年齡"]}$${lastRow},\">=${lo}\",'原始資料'!$${field["年齡"]}$2:$${field["年齡"]}$${lastRow},\"<=${hi}\",'原始資料'!$${field["年齡"]}$2:$${field["年齡"]}$${lastRow},\"<>\")`);
ageFx.push(`=SUMIFS('原始資料'!$${field["件數"]}$2:$${field["件數"]}$${lastRow},'原始資料'!$${field["年齡"]}$2:$${field["年齡"]}$${lastRow},\">=71\",'原始資料'!$${field["年齡"]}$2:$${field["年齡"]}$${lastRow},\"<>\")`);
ageFx.push(`=SUM('原始資料'!$${field["件數"]}$2:$${field["件數"]}$${lastRow})-SUM(E42:E49)`);
ageFx.push("=SUM(E42:E50)");
sheet.getRange("E42:E51").formulas = ageFx.map(formula => [formula]);
sheet.getRange("D42:E50").format.borders = { preset: "insideHorizontal", style: "thin", color: "#D9E2F3" };
sheet.getRange("E42:E51").format = { fill: "#DDEBF7", numberFormat: "#,##0" };
sheet.getRange("D51:E51").format = { fill: "#D9EAF7", font: { bold: true }, numberFormat: "#,##0", borders: { preset: "doubleBottom", style: "thin", color: "#7F8C8D" } };
section("G", "H", "易肇事車種", vehicles, field["當事者區分"], 43, 64);

for (const [column, width] of [["A",28],["B",13],["C",4],["D",32],["E",13],["F",4],["G",34],["H",13]]) sheet.getRange(`${column}:${column}`).format.columnWidth = width;
sheet.getRange("A1:H64").format.wrapText = false;
sheet.freezePanes.freezeRows(4);

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const out = await SpreadsheetFile.exportXlsx(wb);
await out.save(outputPath);

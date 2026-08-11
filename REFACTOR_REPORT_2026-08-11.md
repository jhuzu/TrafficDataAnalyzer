# TrafficDataAnalyzer 架構問題修正報告

> 修正日期：2026-08-11
> 修正範圍：localhost 後端、Session、簡報生成入口、前端模組、Canvas 圖表、Node runtime、下載檔名、測試與文件
> 部署範圍：維持每位承辦人在自己的電腦使用 localhost；未加入帳號系統或多人共用伺服器

---

## 一、本次處理結果

| 原評估問題 | 處理結果 | 狀態 |
|---|---|---|
| 後端沒有 logging | 加入標準 logging；可預期的輸入錯誤記 warning，未預期錯誤保留 traceback | ✅ 完成 |
| Node.js 搜尋路徑不一致 | 新增 `core/runtime.py`，統一處理 `NODE_BIN`、PATH、Apple Silicon、Intel Mac 與系統路徑 | ✅ 完成 |
| PPTX subprocess 寫在 `web_server.py` | 抽至事故模組 `presentation/service.py`，HTTP 層只接收請求及回傳檔案 | ✅ 完成 |
| 全域 Session dict 缺少執行緒保護 | 抽成具鎖定、TTL、容量上限的 `InMemorySessionStore` | ✅ 完成 |
| 清除資料只清前端 | 新增 `/clear`，按鈕會同步刪除後端 Session | ✅ 完成 |
| `payload_builder` 重複切片與加總 | `AccidentDataset` 新增 `select`、`subset`、`total`，analysis 與 presentation 共用 | ✅ 完成 |
| 前端 `app.js` 單體化 | 拆成 API、圖表、地圖、投影片模組；`app.js` 只負責頁面協調 | ✅ 完成 |
| `analyze` 被 monkey-patch 並重綁事件 | 移除覆寫與二次綁定；地圖更新改為明確流程 | ✅ 完成 |
| 快速切換造成重複請求 | 新增 `AbortController` 封裝，新請求會取消同類舊請求 | ✅ 完成 |
| Canvas 固定尺寸、不會隨視窗重繪 | 改用 `ResizeObserver`、實際容器寬度與 device pixel ratio 重繪 | ✅ 完成 |
| Canvas 字型只寫 Microsoft JhengHei | 改為跨平台 system font stack，仍優先支援微軟正黑體 | ✅ 完成 |
| HTML escape 未處理單引號 | `esc()` 新增 `'` → `&#39;` | ✅ 完成 |
| 中文下載檔名被 ASCII 移除 | Content-Disposition 加入 RFC 5987 `filename*=UTF-8''...` | ✅ 完成 |
| 沒有 `package.json` | 新增依賴版本、Node 版本與語法檢查 scripts | ✅ 完成 |
| 無法交付其他承辦人直接安裝 | 已明確標出 runtime symlink 限制；離線安裝包仍是後續交付工作 | 🟡 已界定，未封裝 |

---

## 二、後端架構修正

### 1. HTTP 與簡報生成責任分離

修正前：

```text
web_server.py
└─ 驗證版本 → 找 Node → 建 tempdir → 寫 JSON → subprocess → 讀 PPTX → HTTP 回傳
```

修正後：

```text
web_server.py
└─ 取得 Session → 呼叫 AccidentPresentationService → HTTP 回傳

modules/accident_analysis/presentation/service.py
└─ 版本設定 → 模板檢查 → Node 程序 → 暫存檔生命週期 → GeneratedPresentation
```

效果：

- `web_server.py` 不再知道 generator 參數與暫存檔細節。
- 新式與傳統版仍共用同一份 `accident-weekly-report/v1` payload。
- Presentation service 可獨立 mock 測試，也已用真實 Node generator 各生成一次驗證。

### 2. Session 儲存邊界

新增 `core/session_store.py`：

- 使用 `RLock` 保護 `ThreadingHTTPServer` 的同時存取。
- 每次讀取會刷新最後使用時間。
- 30 分鐘未使用自動失效。
- 最多保留 10 組 Session，超過時移除最舊資料。
- `create`、`get`、`delete` 與 `cleanup` 已形成可替換介面。

目前仍刻意使用記憶體，因為部署方式是「每位承辦人自己的 localhost」。未加入帳號、資料庫、區網監聽或多人共享。

### 3. Logging 與錯誤回應

- 400 類輸入錯誤：終端機留下 warning，前端顯示可理解的原因。
- 500 類程式錯誤：終端機保留完整 traceback，前端不直接暴露內部例外細節。
- HTTP 存取會進入標準 logger，不再完全靜默。

### 4. 統計共用範圍

已抽成 `AccidentDataset` 共用方法：

- `total()`：依既有數字正規化規則加總。
- `select()`：依欄位值篩選，集中處理欄位位置與文字轉換。
- `subset()`：保留來源 metadata 的不可變子資料集。

以下仍保留在 `payload_builder.py`，屬於簡報報表規格，不是一般基礎分析規則：

- A1／A2 與前一年度同期比較。
- 事故年齡固定區間。
- 2 小時事故時段區間。
- A1 明細最多 7 筆。
- 週報用摘要與勤務建議文字。

這項安排避免為了表面上的「完全共用」而讓一般分析 service 混入簡報版面規則。

---

## 三、前端架構修正

### 1. 檔案責任

```text
frontend/
├─ app.js       # 狀態、畫面渲染、事件協調
├─ api.js       # fetch、錯誤解析、AbortController
├─ chart.js     # 回應式 Canvas 排行圖
├─ map.js       # Leaflet 地圖與事故標記
├─ slides.js    # 新式／傳統 PPTX 下載流程
├─ modules.js   # sidebar 功能註冊
├─ index.html   # 頁面骨架
└─ styles.css   # 共用樣式
```

`index.html` 已改用原生 ES modules，不需要 bundler 或額外前端框架。

### 2. 請求競態處理

同類請求只保留最新一次：

```text
使用者快速切換篩選
├─ 舊 /analyze → abort
└─ 新 /analyze → 完成後更新畫面
```

因此較慢的舊回應不會覆蓋較新的篩選結果。

### 3. Canvas 回應式圖表

- 依可見容器寬度計算，不再強制最小 760px。
- 高度依顯示筆數在合理範圍內調整。
- 使用最高 2 倍 device pixel ratio，避免高解析度螢幕模糊。
- 容器尺寸改變時延遲 100ms 重繪，避免視窗拖動時連續大量運算。
- 圖表分頁隱藏時不強制繪圖，顯示後再依實際寬度繪製。

### 4. 清除資料流程

```text
按下「清除資料」
├─ 取消載入／分析／簡報中的舊請求
├─ POST /clear 刪除後端 Session
├─ 清除檔案、統計、趨勢、摘要、圖表與地圖標記
├─ 重設篩選與統計期間
└─ 回到「統計表格」分頁
```

即使 Session 已逾時或服務剛重啟，前端仍能完成本機畫面重設。

---

## 四、Runtime 與交付限制

### 1. Node.js 搜尋順序

`core/runtime.py` 依序檢查：

1. 環境變數 `NODE_BIN`
2. 系統 PATH 的 `node`
3. `/opt/homebrew/bin/node`
4. `/usr/local/bin/node`
5. `/usr/bin/node`

網頁簡報生成與 `TrafficDataAnalyzer.command` 已採相同 Python helper。

### 2. `package.json`

已記錄：

- Node.js `>=20`
- `@oai/artifact-tool` `2.8.39`
- `sharp` `0.34.5`
- `npm run check`
- `npm run test:python`

### 3. 其他承辦人使用前仍需處理

目前 `node_modules` 是指向個人 Codex runtime 的 symlink，不能直接複製到其他電腦使用；且 `@oai/artifact-tool` 是 private package。要正式交付其他承辦人，仍需另外製作合法、固定版本、可離線安裝的 runtime 套件，或將生成器改成可公開部署的依賴。

這不是本次程式錯誤，而是部署封裝問題。本次沒有假裝用一份無法安裝的 lockfile 解決它。

---

## 五、新增與修改檔案

### 新增

| 檔案 | 用途 |
|---|---|
| `core/runtime.py` | Node runtime 搜尋 |
| `core/session_store.py` | 執行緒安全 Session 儲存 |
| `frontend/api.js` | API 與取消舊請求 |
| `frontend/chart.js` | 回應式 Canvas 圖表 |
| `frontend/map.js` | Leaflet 地圖模組 |
| `frontend/slides.js` | PPTX 下載模組 |
| `modules/accident_analysis/presentation/service.py` | 事故簡報生成 service |
| `tests/test_runtime_services.py` | Runtime、Session、下載檔名與簡報 service 測試 |
| `package.json` | Node 版本、依賴與檢查指令 |
| `REFACTOR_REPORT_2026-08-11.md` | 本修正報告 |

### 主要修改

| 檔案 | 修改摘要 |
|---|---|
| `web_server.py` | logging、SessionStore、`/clear`、UTF-8 檔名、presentation service |
| `frontend/app.js` | 移除 monkey-patch，改為模組協調器 |
| `frontend/index.html` | `app.js` 改以 ES module 載入 |
| `frontend/styles.css` | Canvas 高度改為回應式 |
| `modules/accident_analysis/data/transformer.py` | 新增 `total`、`select`、`subset` |
| `modules/accident_analysis/analysis/service.py` | 件數改用 dataset 共用加總 |
| `modules/accident_analysis/presentation/payload_builder.py` | 共用資料切片與加總 |
| `TrafficDataAnalyzer.command` | 共用 Node 搜尋 helper |
| `README.md`、`ARCHITECTURE.md`、`TODO.md` | 更新架構、部署邊界與待辦 |

---

## 六、驗證結果

### 1. Python 單元測試

- Python 3.14 環境：18／18 通過。
- macOS 系統 `/usr/bin/python3` 3.9.6：18／18 通過。
- 測試包含 Excel reader、Pivot Cache、transformer、事故分析、地圖聚合、presentation payload、Session TTL／容量、Node 搜尋、UTF-8 檔名與 presentation service。

### 2. Node／前端語法

`npm run check` 全部通過：

- 5 個前端 ES modules。
- `build_xlsx.mjs`。
- 新式與傳統 presentation generator。

### 3. 真實簡報生成

透過新的 `AccidentPresentationService`，不是 mock：

| 版本 | 結果 | 輸出大小 |
|---|---|---:|
| 新式版本 | 成功 | 239,740 bytes |
| 傳統版本 | 成功 | 1,285,665 bytes |

### 4. localhost API

使用合成 Excel 實測：

- `/load`：辨識一般工作表，載入 2 列。
- `/analyze`：依「件數」加總 3 件，路段排行與月份趨勢正確。
- `/clear`：回傳成功。
- 清除後用原 token 呼叫 `/analyze`：正確回覆資料已失效。

### 5. 瀏覽器畫面

- ES modules 全部載入，console 無 error／warning。
- 上傳 Excel 後，4 張 KPI、2 列排行與摘要正常。
- 統計圖表在 943px 容器中以 1,886px 實際 Canvas 寬度繪製。
- 清除後 KPI 歸零、表格顯示「尚未載入資料」、tab 回「統計表格」。

### 6. 其他檢查

- `zsh -n TrafficDataAnalyzer.command`：通過。
- `zsh -n 啟動網頁版.command`：通過。
- `git diff --check`：通過。
- 重構後版本已啟動於 `http://127.0.0.1:8765`。

---

## 七、刻意未做與後續待辦

### 本次刻意未做

- 不做帳號系統。
- 不做多人共用伺服器。
- 不改成區網監聽。
- 不新增資料庫。
- 不刪除 `major_violation` 佔位模組，因為後續仍會實作。
- 不把簡報專屬年齡／時段／A1 規格塞進一般分析 service。

### 後續真正需要的工作

1. 製作可交付其他承辦人的離線 runtime／安裝包。
2. 建立 PPTX TOKEN 完整性與版面回歸測試。
3. 抽出新式／傳統 generator 共用的 PPTX 物件搜尋、文字與表格填值 helper。
4. 實作重大違規績效模組時，沿用 `data → analysis → presentation` 介面，不複製事故規則。

---

## 八、最後 Check 建議

請依序人工確認：

1. 重新整理 `http://127.0.0.1:8765`。
2. 載入實際 `.xlsm`，核對總數與原 Excel「件數」合計。
3. 快速切換酒駕／毒駕／行人與顯示筆數，確認畫面只留下最後選項。
4. 切換統計圖表並調整瀏覽器寬度，確認圖表重繪。
5. 點清除資料後再按顯示分析，確認不會沿用舊資料。
6. 各生成一次新式與傳統投影片，人工檢查模板版面與填值。
7. 確認無誤後再建立本次 Git commit。

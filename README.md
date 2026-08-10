# TrafficDataAnalyzer

本機端交通資料分析工具。現階段支援：

- 讀取含 Pivot Cache 的 `.xlsm`
- 事故資料的路段、路口、時段、肇因、年齡與車種分析
- 趨勢表、圖表、熱點地圖與摘要
- 依骨架模板生成交通事故分析週報 PPTX
- 清除目前 session，回到未載入狀態

## 啟動

```bash
./啟動網頁版.command
```

或執行：

```bash
python3 web_server.py
```

瀏覽器開啟 `http://127.0.0.1:8765`。

## 目錄與模組化

頂層 sidebar 不直接寫死功能，改由 `frontend/modules.js` 的模組註冊表產生。未來新增「人口資料分析」或其他資料模組時，只需新增模組設定與對應 view，再逐步抽離該模組的分析邏輯。

詳細說明請見 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 注意事項

- 原始 Excel 與 PPT 模板不放入版本控制；請依個資與機關資料規範管理。
- `node_modules` 為本機 runtime symlink，不應提交。
- 生成檔請放入 `generated/`，測試與暫存檔請放入 `tmp/`。

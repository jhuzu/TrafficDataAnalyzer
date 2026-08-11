# 事故資料分析模組

此模組只放事故資料專用功能：

- `data/transformer.py`：將共用 Excel reader 的輸出轉成事故專屬 `AccidentDataset`
- `analysis/service.py`：事故樣態篩選、排行、趨勢、摘要、原始資料分頁及地圖標記
- `presentation/payload_builder.py`：將事故統計轉為兩套簡報共用的版本化 payload
- `presentation/*.mjs`：只負責新式／傳統模板填值、圖表繪製及 PPTX 輸出
- `templates/`：事故週報骨架模板與 TOKEN 對照表

`web_server.py` 只負責 HTTP、session 與簡報程序呼叫；不得在路由內新增事故統計規則。新增事故分析項目時，應修改 `analysis/service.py` 並補上對應測試。

新增事故分析欄位或投影片 TOKEN 時，請優先在此模組內修改，避免影響其他資料分析模組。

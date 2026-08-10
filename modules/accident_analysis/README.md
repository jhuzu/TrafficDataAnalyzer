# 事故資料分析模組

此模組只放事故資料專用功能：

- `presentation/`：事故週報 PPT 生成與骨架模板建置工具
- `templates/`：事故週報骨架模板與 TOKEN 對照表
- 基礎分析目前仍由 `frontend/app.js` 與 `web_server.py` 提供，後續可再拆到本模組的 `analysis/`。

新增事故分析欄位或投影片 TOKEN 時，請優先在此模組內修改，避免影響其他資料分析模組。

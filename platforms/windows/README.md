# TrafficDataAnalyzer Windows 使用說明

適用於 Windows 10、11（64 位元）。

## 要點哪一個？

### 這台電腦已經安裝完成

平常使用只要連按兩下：

**`啟動Windows版.bat`**

啟動後會自動打開瀏覽器，網址為：

<http://127.0.0.1:8765/>

請保留啟動後的命令提示字元視窗；關閉該視窗就會停止工具。

### 第一次在其他 Windows 電腦使用

1. 安裝 [Python 3.11 或更新版本](https://www.python.org/downloads/windows/)。
2. 安裝 Python 時勾選 **Add Python to PATH**。
3. 完整解壓或 clone 專案，不要只複製 `platforms/windows` 資料夾。
4. 開啟 `platforms/windows` 資料夾。
5. 連按兩下 **`安裝Windows依賴.bat`**，等待專案內的 `.venv` 建立完成。
6. 連按兩下 **`啟動Windows版.bat`**。

所有 Python 套件都安裝在專案的 `.venv` 中，不會安裝到全域 Python 環境。

## 檔案用途

| 檔案 | 用途 |
| --- | --- |
| `啟動Windows版.bat` | 平常啟動工具 |
| `安裝Windows依賴.bat` | 第一次安裝或重建 `.venv` |
| `打包Windows免安裝版.bat` | 供開發者製作可交付的免安裝 ZIP |
| `windows_launcher.py` | 免安裝版的 Python 入口，一般使用者不需直接開啟 |

## 使用資料

- 支援 `.xlsx` 與 `.xlsm`。
- 舊版 `.xls` 請先在 Excel 另存為 `.xlsx`。
- 上傳的資料在本機程式與 `127.0.0.1` 之間處理。
- 地圖定位使用專案內建的板橋道路參考資料；OpenStreetMap 底圖需要網路。

## 停止工具

關閉執行 `啟動Windows版.bat` 後出現的命令提示字元視窗，或在該視窗按 `Ctrl+C`。

## 常見問題

### 顯示 8765 連接埠已被使用

工具可能已經啟動。新版啟動腳本會直接開啟現有的 <http://127.0.0.1:8765/>，不會再把這種情況視為錯誤。

### Windows 阻擋 `.bat`

確認檔案來自信任的專案後，可在 Windows 安全性提示中選擇「其他資訊」→「仍要執行」。

### 啟動後瀏覽器沒有自動打開

手動開啟 <http://127.0.0.1:8765/>。若仍無法連線，請回到命令提示字元視窗查看錯誤訊息。

## 開發者啟動方式

在專案根目錄執行：

```powershell
.\.venv\Scripts\python.exe web_server.py
```

然後開啟 <http://127.0.0.1:8765/>。

執行測試：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

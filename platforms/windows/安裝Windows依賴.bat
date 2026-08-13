@echo off
setlocal
set "PROJECT_ROOT=%~dp0..\.."
cd /d "%PROJECT_ROOT%"

where py >nul 2>nul && (set "PYTHON=py -3") || (set "PYTHON=python")
%PYTHON% --version >nul 2>nul || (
  echo [錯誤] 找不到 Python 3。
  echo 請至 https://www.python.org/downloads/windows/ 安裝 Python 3.11 或更新版本，
  echo 安裝時請勾選 "Add Python to PATH"，再重新執行本檔。
  pause
  exit /b 1
)

%PYTHON% -m venv .venv
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo 安裝完成。請連按兩下「啟動Windows版.bat」。
pause
exit /b 0

:error
echo.
echo [錯誤] 安裝失敗。請確認網路連線與 Python 安裝狀態後再試。
pause
exit /b 1

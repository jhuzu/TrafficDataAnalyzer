@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" call "安裝Windows依賴.bat"
if errorlevel 1 exit /b 1

.venv\Scripts\python.exe -m pip install pyinstaller
if errorlevel 1 goto :error

set "RELEASE=generated\TrafficDataAnalyzer_Windows_免安裝版"
if exist "%RELEASE%" rmdir /s /q "%RELEASE%"
mkdir "%RELEASE%"

.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --name "交通資料分析工具" --distpath "%RELEASE%" --workpath tmp\pyinstaller-work --specpath tmp\pyinstaller-spec --add-data "frontend;frontend" --add-data "modules\accident_analysis\templates;modules\accident_analysis\templates" windows_launcher.py
if errorlevel 1 goto :error

copy /y "Windows使用說明.txt" "%RELEASE%\使用說明.txt" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%RELEASE%' -DestinationPath '%RELEASE%.zip' -Force"
echo.
echo 完成：%RELEASE%.zip
pause
exit /b 0

:error
echo.
echo [錯誤] Windows 免安裝版封裝失敗。
pause
exit /b 1

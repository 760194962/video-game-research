@echo off
chcp 65001 >nul
rem Test that each candidate really runs: "python" may be the Microsoft Store stub,
rem and "py" may point at a removed install.
for %%P in ("python" "py -3" "%LOCALAPPDATA%\Python\bin\python.exe") do (
    %%~P -c "" >nul 2>nul && (%%~P "%~dp0ngb_save_manager.py" %* & goto :end)
)
echo 没有找到 Python，请先安装 Python 3（python.org，安装时勾选 Add to PATH）。
echo Python not found. Please install Python 3 from python.org and tick "Add to PATH" during setup.
pause
:end
if errorlevel 1 pause

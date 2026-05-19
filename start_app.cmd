@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\.runtime_pkgs"
echo Starting Ronisens Product QA MVP...
echo.
echo Browser URL:
echo   http://127.0.0.1:8501
echo.
echo Keep this window open while testing. Press Ctrl+C to stop.
echo.
".runtime_pkgs\bin\streamlit.exe" run app.py --server.port 8501 --server.address 127.0.0.1
endlocal

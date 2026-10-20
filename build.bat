@echo off
setlocal
cd /d "%~dp0"
if exist .venv312\Scripts\python.exe (
  set "LF_PY=.venv312\Scripts\python.exe"
) else (
  set "LF_PY=.venv\Scripts\python.exe"
)
if not exist %LF_PY% (
  py -3.11 -m venv .venv
  if errorlevel 1 exit /b 1
)
%LF_PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 exit /b 1
%LF_PY% -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
%LF_PY% -m pytest -q
if errorlevel 1 exit /b 1
set LAUNCHFLOW_ONEFILE=0
if "%~1"=="onefile" set LAUNCHFLOW_ONEFILE=1
%LF_PY% -m PyInstaller --noconfirm launchflow.spec
if errorlevel 1 exit /b 1
endlocal

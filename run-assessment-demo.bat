@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  python main.py --demo --demo-date 2030-01-07
) else (
  py -3 main.py --demo --demo-date 2030-01-07
)
if errorlevel 1 pause

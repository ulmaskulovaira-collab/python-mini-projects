@echo off
cd /d "%~dp0"
title Build Catch The Stars EXE

where py >nul 2>nul
if errorlevel 1 (
    echo Python was not found.
    pause
    exit /b 1
)

echo Installing build tools...
py -m pip install -r requirements-dev.txt
if errorlevel 1 (
    echo Installation failed.
    pause
    exit /b 1
)

echo Building CatchTheStars.exe...
py -m PyInstaller --noconfirm --clean --onefile --windowed --name CatchTheStars --add-data "assets;assets" main.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Ready: dist\CatchTheStars.exe
start "" "%~dp0dist"
pause

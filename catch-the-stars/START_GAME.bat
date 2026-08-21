@echo off
cd /d "%~dp0"
title Catch the Stars

where py >nul 2>nul
if errorlevel 1 (
    echo Python was not found.
    echo Install Python from python.org and enable Add Python to PATH.
    pause
    exit /b 1
)

py -c "import pygame" >nul 2>nul
if errorlevel 1 (
    echo Installing Pygame. Please wait...
    py -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Pygame installation failed. Check your internet connection.
        pause
        exit /b 1
    )
)

py main.py

if errorlevel 1 (
    echo.
    echo The game stopped with an error.
    pause
)

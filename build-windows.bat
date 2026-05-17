@echo off
REM ---------------------------------------------------------------------------
REM build-windows.bat — Package Sample DNA Tagger as a Windows executable.
REM
REM Prerequisites:
REM   - Python 3.11+ with pyinstaller installed (pip install pyinstaller)
REM   - Node.js 18+
REM   - Project dependencies installed (pip install -e ".[dev]")
REM
REM Output:  dist\Sample DNA Tagger\Sample DNA Tagger.exe
REM ---------------------------------------------------------------------------
setlocal

cd /d "%~dp0"

echo === Building frontend ===
cd frontend && call npm run build && cd ..

echo.
echo === Cleaning previous builds ===
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo.
echo === Running PyInstaller ===
pyinstaller SampleDNA.spec --clean --noconfirm

echo.
echo === Build complete ===
echo Executable: dist\Sample DNA Tagger\Sample DNA Tagger.exe

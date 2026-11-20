@echo off
chcp 65001 >nul
title PS5 Dich Game - Cai dat va chay
echo ===============================================
echo   PS5 Dich Game - Cai dat va chay (chay tu code)
echo ===============================================
echo.

REM 1. Kiem tra Python
py --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay Python.
    echo Hay cai Python 3.10 tro len tu https://www.python.org/downloads/
    echo (luc cai nho tick "Add python.exe to PATH"), roi chay lai file nay.
    pause
    exit /b 1
)

REM 2. Kiem tra Tesseract, neu chua co thi thu cai bang winget
where tesseract >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
        echo Da thay Tesseract tai C:\Program Files\Tesseract-OCR
    ) else (
        echo Chua thay Tesseract. Dang thu cai bang winget...
        winget install -e --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements >nul 2>&1
        where tesseract >nul 2>&1
        if errorlevel 1 (
            if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
                echo [CANH BAO] Khong cai duoc Tesseract tu dong.
                echo Hay tai ban cai tai https://github.com/UB-Mannheim/tesseract/wiki
                echo (file tesseract-ocr-w64-setup-*.exe) roi cai, sau do chay lai.
                pause
            )
        )
    )
)

REM 3. Cai thu vien Python
echo Dang cai thu vien Python...
py -m pip install --upgrade pip >nul 2>&1
py -m pip install -r requirements.txt
if errorlevel 1 (
    echo [LOI] Cai thu vien that bai. Kiem tra mang roi chay lai.
    pause
    exit /b 1
)

REM 4. Chay app
echo.
echo Cai dat xong. Dang mo PS5 Dich Game...
py run.py
pause

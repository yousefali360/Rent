# سكربت تشغيل محرك البحث العربي عن شقق الإيجار في بنها على Windows PowerShell
$ErrorActionPreference = "Stop"

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "  محرك البحث عن شقق الإيجار - بنها، محافظة القليوبية" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[+] تم إنشاء ملف .env من .env.example" -ForegroundColor Green
}

Write-Host "[*] تشغيل الخادم على http://127.0.0.1:8000 ..." -ForegroundColor Yellow
& ".\.venv\Scripts\uvicorn.exe" backend.app.main:app --host 127.0.0.1 --port 8000 --reload

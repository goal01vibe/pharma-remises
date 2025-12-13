@echo off
echo ========================================
echo    Pharma Remises - Arret
echo ========================================
echo.

:: Arreter le backend (uvicorn/python sur port 8847)
echo [1/3] Arret Backend...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8847 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Arreter le frontend (node/vite sur port 5174)
echo [2/3] Arret Frontend...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5174 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Fermer les fenetres CMD associees
taskkill /FI "WINDOWTITLE eq Pharma-Remises Backend" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Pharma-Remises Frontend" /F >nul 2>&1

:: Arreter PostgreSQL
echo [3/3] Arret PostgreSQL...
cd /d C:\pharma-remises
docker-compose down

echo.
echo ========================================
echo    Application arretee !
echo ========================================
pause

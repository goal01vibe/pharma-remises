@echo off
echo ========================================
echo    Pharma Remises - Arret
echo ========================================
echo.

:: Arreter les fenetres CMD (backend/frontend)
echo [1/2] Arret Backend et Frontend...
taskkill /FI "WINDOWTITLE eq Pharma-Remises*" /F >nul 2>&1

:: Arreter PostgreSQL
echo [2/2] Arret PostgreSQL...
cd /d C:\pharma-remises
docker-compose down

echo.
echo Application arretee.
pause

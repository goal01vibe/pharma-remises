@echo off
echo ========================================
echo    Pharma Remises - Demarrage
echo ========================================
echo.

:: Verifier si Docker est lance
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Docker n'est pas lance. Demarrez Docker Desktop.
    pause
    exit /b 1
)

:: Demarrer PostgreSQL
echo [1/3] Demarrage PostgreSQL...
cd /d C:\pharma-remises
docker-compose up -d
timeout /t 3 /nobreak >nul

:: Demarrer le backend
echo [2/3] Demarrage Backend (port 8847)...
start "Pharma-Remises Backend" cmd /k "cd /d C:\pharma-remises\backend && python -m uvicorn main:app --reload --port 8847"

:: Attendre que le backend soit pret (health check)
echo      Attente du backend...
:wait_backend
timeout /t 2 /nobreak >nul
curl -s http://localhost:8847/health >nul 2>&1
if errorlevel 1 (
    echo      Backend pas encore pret, nouvelle tentative...
    goto wait_backend
)
echo      Backend OK!

:: Demarrer le frontend
echo [3/3] Demarrage Frontend (port 5174)...
start "Pharma-Remises Frontend" cmd /k "cd /d C:\pharma-remises\frontend && npm run dev"

echo.
echo ========================================
echo    Application demarree !
echo ========================================
echo.
echo    Frontend: http://localhost:5174
echo    Backend:  http://localhost:8847
echo    API Docs: http://localhost:8847/docs
echo.
echo Appuyez sur une touche pour ouvrir le navigateur...
pause >nul

start http://localhost:5174

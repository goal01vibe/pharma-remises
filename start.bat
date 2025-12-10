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
echo [2/3] Demarrage Backend (port 8003)...
start "Pharma-Remises Backend" cmd /k "cd /d C:\pharma-remises\backend && python -m uvicorn main:app --reload --port 8003"
timeout /t 2 /nobreak >nul

:: Demarrer le frontend
echo [3/3] Demarrage Frontend (port 5174)...
start "Pharma-Remises Frontend" cmd /k "cd /d C:\pharma-remises\frontend && npm run dev"

echo.
echo ========================================
echo    Application demarree !
echo ========================================
echo.
echo    Frontend: http://localhost:5174
echo    Backend:  http://localhost:8003
echo    API Docs: http://localhost:8003/docs
echo.
echo Appuyez sur une touche pour ouvrir le navigateur...
pause >nul

start http://localhost:5174

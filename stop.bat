@echo off
echo ========================================
echo    Pharma Remises - Arret
echo ========================================
echo.

:: Arreter le backend (uvicorn/python sur port 8847)
echo [1/3] Arret Backend (port 8847)...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8847" ^| findstr "LISTENING"') do (
    echo       Arret PID %%a
    taskkill /PID %%a /F /T >nul 2>&1
)
:: Tuer aussi les processus uvicorn directement
taskkill /IM uvicorn.exe /F >nul 2>&1
:: Tuer python qui ecoute sur ce port
for /f "tokens=2" %%a in ('wmic process where "commandline like '%%uvicorn%%8847%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /PID %%a /F /T >nul 2>&1
)

:: Arreter le frontend (node/vite sur port 5174)
echo [2/3] Arret Frontend (port 5174)...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5174" ^| findstr "LISTENING"') do (
    echo       Arret PID %%a
    taskkill /PID %%a /F /T >nul 2>&1
)
:: Tuer les processus node qui font tourner vite
for /f "tokens=2" %%a in ('wmic process where "commandline like '%%vite%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /PID %%a /F /T >nul 2>&1
)

:: Fermer les fenetres CMD associees
echo       Fermeture des fenetres...
taskkill /FI "WINDOWTITLE eq Pharma-Remises Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Pharma-Remises Frontend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq *pharma-remises*" /F >nul 2>&1

:: Attendre un peu pour que les processus se terminent
timeout /t 2 /nobreak >nul

:: Arreter PostgreSQL Docker
echo [3/3] Arret PostgreSQL...
cd /d C:\pharma-remises
docker-compose down 2>nul

:: Verification finale
echo.
echo Verification des ports...
netstat -ano | findstr ":8847" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [!] ATTENTION: Port 8847 encore occupe
) else (
    echo [OK] Port 8847 libere
)
netstat -ano | findstr ":5174" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [!] ATTENTION: Port 5174 encore occupe
) else (
    echo [OK] Port 5174 libere
)

echo.
echo ========================================
echo    Application arretee !
echo ========================================
pause

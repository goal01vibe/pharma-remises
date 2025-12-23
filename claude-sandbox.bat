@echo off
REM Lance Claude Code dans un environnement Docker isole
REM Usage: claude-sandbox.bat [options]
REM   Sans argument: lance Claude interactif
REM   --build: reconstruit l'image avant de lancer

setlocal

set IMAGE_NAME=claude-pharma
set CONTAINER_NAME=claude-sandbox

REM Verifier si Docker est lance
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Docker n'est pas lance. Demarre Docker Desktop d'abord.
    pause
    exit /b 1
)

REM Option --build pour reconstruire l'image
if "%1"=="--build" (
    echo [INFO] Construction de l'image Docker...
    docker build -t %IMAGE_NAME% .
    if errorlevel 1 (
        echo [ERREUR] Echec de la construction de l'image.
        pause
        exit /b 1
    )
    echo [OK] Image construite avec succes.
    shift
)

REM Verifier si l'image existe
docker image inspect %IMAGE_NAME% >nul 2>&1
if errorlevel 1 (
    echo [INFO] Image non trouvee. Construction en cours...
    docker build -t %IMAGE_NAME% .
    if errorlevel 1 (
        echo [ERREUR] Echec de la construction de l'image.
        pause
        exit /b 1
    )
)

echo.
echo ============================================
echo   Claude Code Sandbox - Pharma Remises
echo ============================================
echo.
echo [INFO] Lancement de Claude en mode sandbox...
echo [INFO] Repertoire monte: %CD%
echo [INFO] Pour quitter: tapez 'exit' ou Ctrl+D
echo.

REM Lancer le container avec:
REM   -it: mode interactif
REM   --rm: supprime le container apres arret
REM   -v: monte le repertoire courant dans /workspace
REM   --network host: acces au PostgreSQL local (port 5433)
docker run -it --rm ^
    --name %CONTAINER_NAME% ^
    -v "%CD%":/workspace ^
    -v %USERPROFILE%\.claude:/root/.claude ^
    --network host ^
    -e ANTHROPIC_API_KEY=%ANTHROPIC_API_KEY% ^
    %IMAGE_NAME% ^
    claude --dangerously-skip-permissions

echo.
echo [INFO] Session Claude terminee.

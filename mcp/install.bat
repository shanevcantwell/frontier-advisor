@echo off
setlocal enabledelayedexpansion

:: ─────────────────────────────────────────────
::  frontier-advisor installer (Windows)
:: ─────────────────────────────────────────────

set "REPO_DIR=%~dp0"
set "IMAGE_NAME=mcp/frontier-advisor"
set "ERROR_LOG=%REPO_DIR%install-error.log"
set "OPENAI_LINE="

echo.
echo   +-------------------------------------------+
echo   :       frontier-advisor  setup             :
echo   +-------------------------------------------+
echo.
echo   1)  Docker                 (claude CLI / OAuth, recommended)
echo   2)  Docker MCP Toolkit     (gateway + mcp.json)
echo.
set /p "CHOICE=  Pick an option [1/2]: "

if "%CHOICE%"=="1" goto dockerrun
if "%CHOICE%"=="2" goto toolkit
echo.
echo   ! Invalid choice. Run this script again.
exit /b 1

:: ── Build ────────────────────────────────────

:build
echo.
echo   Building Docker image (bundles the claude CLI)...
docker build -t %IMAGE_NAME% "%REPO_DIR%." --quiet >nul 2>>"%ERROR_LOG%"
if errorlevel 1 (
    echo   X Docker build failed. See install-error.log for details.
    echo     Is Docker Desktop running?
    exit /b 1
)
echo   * Image built: %IMAGE_NAME%
exit /b 0

:: ── Shared: claude CLI OAuth prerequisite ────

:check_claude_auth
echo.
echo   Top tier: local claude CLI (Opus via OAuth / flat-rate Claude Max)
echo.
if exist "%USERPROFILE%\.claude\.credentials.json" (
    echo   * Found OAuth credentials at %%USERPROFILE%%\.claude\.credentials.json
) else (
    echo   ! No %%USERPROFILE%%\.claude\.credentials.json found.
    echo     Authenticate the CLI once on the host, then re-run if needed:
    echo       claude        ^(sign in via OAuth, then exit^)
    echo     The container mounts ~/.claude read-only -- no API key is baked or needed.
)
exit /b 0

:: ── Shared: optional OpenAI fallback ─────────

:prompt_openai
echo.
echo   Optional: OpenAI fallback tier (GPT-4.1)
echo   Used only when the claude CLI tier is unavailable. Press Enter to skip.
set /p "OPENAI_KEY=  OPENAI_API_KEY (Enter to skip): "
if defined OPENAI_KEY (
    set "OPENAI_LINE=        "-e", "OPENAI_API_KEY=!OPENAI_KEY!","
    echo   * OpenAI fallback enabled ^(key will be inlined in the snippet below^)
    echo     Prefer not to inline it? Use mcp-vault: "OPENAI_API_KEY=vault:openai/api-key".
) else (
    echo   Skipped -- top tier ^(claude CLI^) only.
)
exit /b 0

:: ── Shared: config snippet ───────────────────

:print_snippet
echo.
echo   Add this to your MCP client config (mcp.json):
echo.
echo     "frontier-advisor": {
echo       "command": "docker",
echo       "args": [
echo         "run", "-i", "--rm",
echo         "-v", "${HOME}/.claude:/home/advisor/.claude:ro",
if defined OPENAI_LINE echo !OPENAI_LINE!
echo         "mcp/frontier-advisor"
echo       ]
echo     }
echo.
echo   The read-only ~/.claude mount supplies OAuth creds at runtime --
echo   nothing is baked into the image. (Base config also in mcp.json.example.)
echo   On Windows, if your client does not expand ${HOME}, use the literal
echo   path, e.g. "%%USERPROFILE%%\.claude:/home/advisor/.claude:ro".
exit /b 0

:: ── Option 1: Docker ─────────────────────────

:dockerrun
call :build
if errorlevel 1 exit /b 1
call :check_claude_auth
call :prompt_openai
call :print_snippet
goto done

:: ── Option 2: Docker MCP Toolkit ─────────────

:toolkit
call :build
if errorlevel 1 exit /b 1
call :check_claude_auth

echo.
docker mcp version >nul 2>>"%ERROR_LOG%"
if errorlevel 1 (
    echo   X Docker MCP plugin not found.
    echo     Update Docker Desktop to 4.62+ and enable MCP Toolkit.
    exit /b 1
)

docker mcp catalog create %IMAGE_NAME% >nul 2>>"%ERROR_LOG%"
docker mcp catalog add %IMAGE_NAME% %IMAGE_NAME% "%REPO_DIR%docker-mcp-catalog.yaml" --force >nul 2>>"%ERROR_LOG%"
if errorlevel 1 (
    echo   X Failed to add catalog. See install-error.log for details.
    exit /b 1
)

docker mcp server enable %IMAGE_NAME% >nul 2>>"%ERROR_LOG%"

echo   * Registered in MCP Toolkit (tools visible via gateway)
echo.
echo   Note: Custom catalog servers don't yet appear in the Desktop UI.
echo   Tools are routed through the gateway to connected clients.

call :prompt_openai
call :print_snippet

echo.
echo   Then connect a client:
echo     docker mcp client connect claude
echo     docker mcp client connect cursor
goto done

:: ── Done ─────────────────────────────────────

:done
echo.
echo   Done. See README.md for usage details.
echo.

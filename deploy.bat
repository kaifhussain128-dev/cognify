@echo off
setlocal
echo ===================================================
echo     Cognify (StudyMate AI) - GitHub Deployment
echo ===================================================
echo.
echo [1/3] Checking GitHub CLI Authentication...
"C:\Program Files\GitHub CLI\gh.exe" auth status >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Please authenticate with your GitHub account:
    echo (A browser window will open. Click 'Authorize'.)
    echo.
    "C:\Program Files\GitHub CLI\gh.exe" auth login --web -p https
)

echo.
echo [2/3] Creating GitHub Repository 'cognify' and Pushing Code...
"C:\Program Files\GitHub CLI\gh.exe" repo create cognify --public --source=. --push
if %errorlevel% neq 0 (
    echo.
    echo [Notice] If the repository already exists, pushing directly to main:
    git branch -M main
    git push -u origin main
)

echo.
echo ===================================================
echo   Successfully pushed to GitHub!
echo ===================================================
echo.
echo [3/3] Opening Render New Web Service Dashboard...
echo Select your 'cognify' repository on Render and deploy!
start https://dashboard.render.com/select-repo?type=web
echo.
pause

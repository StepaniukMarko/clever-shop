@echo off
echo ========================================
echo   CLEVER SHOP - DEPLOY TO RAILWAY
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] Checking git status...
git status
echo.

echo [2/4] Adding all changes...
git add .
echo.

echo [3/4] Creating commit...
set /p commit_msg="Enter commit message (or press Enter for default): "
if "%commit_msg%"=="" set commit_msg=Update: %date% %time%

git commit -m "%commit_msg%"
echo.

echo [4/4] Pushing to GitHub...
git push origin main
echo.

echo ========================================
echo   DEPLOY COMPLETE!
echo ========================================
echo.
echo Railway will automatically deploy in 1-2 minutes.
echo Check: https://railway.app
echo.
echo IMPORTANT: Make sure you added these variables in Railway:
echo   - SECRET_KEY
echo   - ADMIN_PASSWORD_HASH  
echo   - TELEGRAM_BOT_TOKEN
echo   - TELEGRAM_CHAT_ID
echo.
echo Run 'python generate_secrets.py' to generate secrets!
echo.
pause
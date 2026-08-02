@echo off
echo ========================================
echo   PiNAS Deploy Package Builder
echo ========================================
echo.

cd /d "%~dp0"

echo Creating deploy package...

if exist deploy.zip del deploy.zip
if exist _deploy_tmp rmdir /s /q _deploy_tmp

mkdir _deploy_tmp
mkdir _deploy_tmp\web
mkdir _deploy_tmp\web\templates

copy web\app.py _deploy_tmp\web\ >nul
copy web\config.py _deploy_tmp\web\ >nul
copy web\requirements.txt _deploy_tmp\web\ >nul
copy web\start.sh _deploy_tmp\web\ >nul
copy web\templates\index.html _deploy_tmp\web\templates\ >nul
copy archive.sh _deploy_tmp\ >nul
copy archive.conf _deploy_tmp\ >nul

powershell -Command "Compress-Archive -Path '_deploy_tmp\*' -DestinationPath 'deploy.zip' -Force"

rmdir /s /q _deploy_tmp

echo.
echo [OK] deploy.zip created
echo.
echo === How to deploy ===
echo.
echo 1. TeraTerm: File - SSH SCP
echo    From: %~dp0deploy.zip
echo    To:   /home/orangepi/
echo.
echo 2. TeraTerm terminal:
echo    bash deploy.sh
echo.
pause

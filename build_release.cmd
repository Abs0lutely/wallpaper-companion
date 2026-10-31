@echo off
setlocal
cd /d "%~dp0"
if exist ".conda\python.exe" goto ready
echo Preparing the project Conda environment...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 goto failed
:ready
"%~dp0.conda\python.exe" -u "%~dp0scripts\release_local.py"
if errorlevel 1 goto failed
echo.
echo SUCCESS. Upload only the files in the verified folder shown above.
pause
exit /b 0
:failed
echo.
echo FAILED. Do not publish this build. See the error and build log above.
echo First run: if Conda is not found, run setup.cmd in Anaconda Prompt first.
pause
exit /b 1

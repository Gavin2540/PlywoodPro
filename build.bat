@echo off
echo ========================================================
echo PlywoodProStandalone Executable Builder
echo ========================================================
echo.

echo [1/3] Installing/Upgrading dependencies from requirements.txt...
python -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Failed to install requirements.
    goto error
)
echo Dependencies successfully verified.
echo.

echo [2/3] Cleaning up prior build structures...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist PlywoodPro.spec del /q PlywoodPro.spec
if exist "Plywood Pro.spec" del /q "Plywood Pro.spec"
echo Cleanup completed.
echo.

echo [3/3] Commencing PyInstaller Compilation (Standalone & Windowed)...
pyinstaller --onefile --windowed --icon=icon.ico --name="Plywood Pro" --add-data "database/schema.sql;database" --add-data "icon.ico;." main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: PyInstaller compilation encountered failures.
    goto error
)
echo.
echo ========================================================
echo SUCCESS: Plywood Pro has been successfully compiled!
echo Standalone executable is located at: dist\Plywood Pro.exe
echo ========================================================
goto end

:error
echo.
echo ========================================================
echo BUILD FAILED: Please check the logs above for diagnostic errors.
echo ========================================================

:end
pause

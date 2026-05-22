@echo off
echo ================================================================
echo   PlywoodPro — Release Builder ^& GitHub Tagger
echo ================================================================
echo.
echo REMINDER: Your GitHub repo MUST be PUBLIC for the auto-updater
echo           to work without a personal access token.
echo.
echo ----------------------------------------------------------------

REM ── Step 0: Ask for the new version number ──────────────────────
set /p NEW_VERSION="Enter the new version number (e.g. 1.0.2): "
if "%NEW_VERSION%"=="" (
    echo ERROR: Version number cannot be empty.
    goto error
)
echo.
echo  New version: v%NEW_VERSION%
echo.

REM ── Step 1: Patch CURRENT_VERSION in updater.py ─────────────────
echo [1/6] Patching CURRENT_VERSION in utils\updater.py ...
python -c "import sys, re; f='utils/updater.py'; txt=open(f, encoding='utf-8').read(); open(f, 'w', encoding='utf-8').write(re.sub(r'CURRENT_VERSION = \".*\"', f'CURRENT_VERSION = \"{sys.argv[1]}\"', txt))" "%NEW_VERSION%"
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to patch updater.py
    goto error
)
echo       Done.
echo.

REM ── Step 2: Install/verify dependencies ─────────────────────────
echo [2/6] Verifying dependencies...
python -m pip install -r requirements.txt >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to install requirements.
    goto error
)
echo       Done.
echo.

REM ── Step 3: Clean and build with PyInstaller ────────────────────
echo [3/6] Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist PlywoodPro.spec del /q PlywoodPro.spec
echo       Done.
echo.

echo [4/6] Building PlywoodPro.exe with PyInstaller...
pyinstaller --onefile --windowed --icon=icon.ico --name=PlywoodPro --add-data "database/schema.sql;database" --add-data "icon.ico;." main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: PyInstaller build failed.
    goto error
)
echo       Build successful.
echo.

REM ── Step 4: Zip the compiled output ─────────────────────────────
echo [5/6] Creating release zip: PlywoodPro_v%NEW_VERSION%.zip ...
if exist "PlywoodPro_v%NEW_VERSION%.zip" del /q "PlywoodPro_v%NEW_VERSION%.zip"
powershell -NoProfile -Command ^
    "Compress-Archive -Path 'dist\PlywoodPro.exe' -DestinationPath 'PlywoodPro_v%NEW_VERSION%.zip' -Force"
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to create zip archive.
    goto error
)
echo       Done. Archive: PlywoodPro_v%NEW_VERSION%.zip
echo.

REM ── Step 5: Git commit and tag ──────────────────────────────────
echo [6/6] Committing, tagging, and pushing to GitHub...
git add -A
git commit -m "release v%NEW_VERSION%"
git tag "v%NEW_VERSION%"
git push origin master --tags
if %ERRORLEVEL% neq 0 (
    echo.
    echo WARNING: Git push may have failed. Check your remote settings.
    echo          You may need to run: git push origin main --tags
    echo          (if your default branch is 'main' instead of 'master')
)
echo       Done.
echo.

REM ── Final: GitHub Release Creation ────────────────────────────────
echo [7/7] Creating GitHub Release and uploading zip...
gh release create "v%NEW_VERSION%" "PlywoodPro_v%NEW_VERSION%.zip" --title "PlywoodPro v%NEW_VERSION%" --notes "Release v%NEW_VERSION%"
if %ERRORLEVEL% neq 0 (
    echo.
    echo WARNING: Failed to create GitHub release via CLI.
    echo          You can still create it manually at:
    echo          https://github.com/Gavin2540/PlywoodPro/releases/new
) else (
    echo.
    echo ================================================================
    echo   BUILD ^& TAG COMPLETE!  v%NEW_VERSION% PUBLISHED!
    echo ================================================================
    echo.
    echo   Once published, all users running PlywoodPro will see the
    echo   update prompt on their next app launch!
    echo.
)
goto end

:error
echo.
echo ================================================================
echo   RELEASE FAILED — check the errors above.
echo ================================================================

:end
pause

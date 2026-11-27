@echo off
echo ========================================================
echo   Plywood Pro - build the Windows .exe
echo ========================================================
python -m pip install -r requirements-dev.txt
if %ERRORLEVEL% neq 0 goto error
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
python -m pytest -q
if %ERRORLEVEL% neq 0 (
    echo Tests failed - not building.
    goto error
)
python tools\build.py
if %ERRORLEVEL% neq 0 goto error
echo.
echo SUCCESS: dist\Plywood Pro.exe
goto end
:error
echo.
echo BUILD FAILED - see the messages above.
:end
pause

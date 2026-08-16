@echo off
setlocal
cd /d "%~dp0"

:try_py
py -3 main.py
if not errorlevel 1 goto done

python main.py
if not errorlevel 1 goto done

echo.
echo Startup failed. Please check the Python and PyQt5 installation.
echo.
pause

:done
endlocal

@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title ArcGIS Pro MCP Server
echo ================================================
echo  ArcGIS Pro MCP Server
echo ================================================
echo.

set PYTHON="e:\arcGIS Pro\bin\Python\envs\arcgispro-py3\python.exe"
set SERVER="%~dp0server.py"

if not exist %PYTHON% (
    echo [ERROR] Python not found: %PYTHON%
    goto :end
)
if not exist %SERVER% (
    echo [ERROR] server.py not found: %SERVER%
    goto :end
)

echo Starting MCP Server...
echo.
%PYTHON% %SERVER%
echo.
echo Server exited with code: %ERRORLEVEL%

:end
echo.
echo Press any key to close...
pause >nul

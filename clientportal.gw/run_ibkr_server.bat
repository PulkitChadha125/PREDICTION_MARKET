@echo off

echo =====================================
echo Starting IBKR Client Portal Gateway
echo =====================================

cd /d "%~dp0"

echo Running gateway...
call bin\run.bat root\conf.yaml

echo =====================================
echo Gateway stopped or crashed
echo =====================================
pause
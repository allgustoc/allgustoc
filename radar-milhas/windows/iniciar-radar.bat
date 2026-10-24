@echo off
rem Abre o painel do Radar de Milhas em http://localhost:8000 e mantem rodando.
rem Se o painel parar por algum erro, ele reinicia sozinho. Feche esta janela para encerrar.
title Radar de Milhas
cd /d "%~dp0.."
if not exist ".venv\Scripts\activate.bat" (
  echo Ambiente nao encontrado em %CD%\.venv
  echo Siga a instalacao do README primeiro.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
start "" /min cmd /c "timeout /t 6 /nobreak >nul & start http://localhost:8000"
:loop
radar web --agendar
echo.
echo O painel parou. Reiniciando em 10 segundos (feche esta janela para encerrar)...
timeout /t 10 /nobreak >nul
goto loop

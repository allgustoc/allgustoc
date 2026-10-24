@echo off
set "ATALHO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Radar de Milhas.lnk"
if exist "%ATALHO%" (
  del "%ATALHO%"
  echo O Radar de Milhas nao abre mais sozinho com o Windows.
) else (
  echo O inicio automatico ja estava desativado.
)
pause

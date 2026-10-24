@echo off
rem Faz o Radar de Milhas abrir sozinho (minimizado) sempre que voce entrar no Windows.
set "ALVO=%~dp0iniciar-radar.bat"
set "PASTA=%~dp0.."
set "ATALHO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Radar de Milhas.lnk"
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:ATALHO); $s.TargetPath = $env:ALVO; $s.WorkingDirectory = $env:PASTA; $s.WindowStyle = 7; $s.Save()"
if exist "%ATALHO%" (
  echo Pronto. O Radar de Milhas vai abrir sozinho quando voce entrar no Windows.
  echo Para desfazer, rode desativar-inicio-automatico.bat
) else (
  echo Nao foi possivel criar o atalho de inicializacao.
)
pause

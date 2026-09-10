@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set "PYTHON_CMD=python"
  ) else (
    echo Python nao encontrado. Instale Python 3.10+ e tente novamente.
    exit /b 1
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual em .venv
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 exit /b 1
)

echo Atualizando pip no .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

echo Instalando dependencias do backend
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 exit /b 1

if not exist ".env" (
    echo Copie o arquivo .env enviado por e-mail para a raiz do projeto
)

if /I "%~1"=="run" (
  ".venv\Scripts\python.exe" -m uvicorn backend.main:app --reload
  exit /b %errorlevel%
)

echo Setup concluido.
echo Para ativar o ambiente: .venv\Scripts\activate
echo Para rodar a API: .venv\Scripts\python.exe -m uvicorn backend.main:app --reload

endlocal

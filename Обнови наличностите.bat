@echo off
chcp 65001 >nul
title Filstar - обновяване на наличностите
cd /d "%~dp0"

echo.
echo  ============================================
echo   Filstar - обновяване на наличностите
echo  ============================================
echo.
echo  ВАЖНО: пуснете VPN преди да продължите.
echo.
pause

set PY=
where python >nul 2>&1 && set PY=python
if "%PY%"=="" (where py >nul 2>&1 && set PY=py -3)
if "%PY%"=="" (where python3 >nul 2>&1 && set PY=python3)

if "%PY%"=="" (
  echo.
  echo  Python не е намерен на този компютър.
  echo.
  echo  1. Отворете https://www.python.org/downloads/
  echo  2. Свалете и инсталирайте Python
  echo  3. ВАЖНО: при инсталацията сложете отметка
  echo     "Add Python to PATH"
  echo  4. Пуснете този файл отново
  echo.
  pause
  exit /b 1
)

echo.
echo  Проверка на библиотеките...
%PY% -m pip install --quiet --upgrade requests
if errorlevel 1 (
  echo  Неуспешна инсталация на requests. Проверете интернет връзката.
  pause
  exit /b 1
)

echo.
%PY% filstar_local.py --skus all_skus.csv
set RC=%errorlevel%

if %RC%==2 (
  echo.
  echo  ------------------------------------------------
  echo   СПРЯНО: сайтът блокира връзката.
  echo   Включете VPN или сменете сървъра на VPN-а,
  echo   после пуснете този файл отново.
  echo   Свалените до момента данни са запазени.
  echo  ------------------------------------------------
  echo.
  pause
  exit /b 2
)

if not %RC%==0 (
  echo.
  echo  Възникна грешка. Пуснете файла отново.
  pause
  exit /b %RC%
)

if %RC%==3 (
  echo.
  echo  ------------------------------------------------
  echo   Данните са свалени успешно, но качването
  echo   в GitHub не стана. Проверете settings.ini.
  echo   Файловете са запазени в тази папка.
  echo  ------------------------------------------------
  echo.
  pause
  exit /b 3
)

echo.
echo  Готово. Наличностите са обновени.
echo.
pause

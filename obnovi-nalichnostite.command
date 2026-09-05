#!/usr/bin/env bash
# Filstar - обновяване на наличностите (macOS / Linux)
cd "$(dirname "$0")" || exit 1

echo
echo " ============================================"
echo "  Filstar - обновяване на наличностите"
echo " ============================================"
echo
echo " ВАЖНО: пуснете VPN преди да продължите."
echo
read -r -p " Натиснете Enter за да започнем..." _

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done

if [ -z "$PY" ]; then
  echo
  echo " Python не е намерен."
  echo " macOS:  отворете Terminal и напишете:  xcode-select --install"
  echo " Или свалете от https://www.python.org/downloads/"
  echo
  read -r -p " Enter за изход..." _
  exit 1
fi

echo
echo " Проверка на библиотеките..."
"$PY" -m pip install --quiet --upgrade requests || {
  echo " Неуспешна инсталация на requests. Проверете интернет връзката."
  read -r -p " Enter за изход..." _
  exit 1
}

echo
"$PY" filstar_local.py --skus all_skus.csv
RC=$?

if [ "$RC" -eq 2 ]; then
  echo
  echo " ------------------------------------------------"
  echo "  СПРЯНО: сайтът блокира връзката."
  echo "  Включете VPN или сменете сървъра на VPN-а,"
  echo "  после пуснете този файл отново."
  echo "  Свалените до момента данни са запазени."
  echo " ------------------------------------------------"
  echo
  read -r -p " Enter за изход..." _
  exit 2
fi

if [ "$RC" -ne 0 ]; then
  echo
  echo " Възникна грешка. Пуснете файла отново."
  read -r -p " Enter за изход..." _
  exit "$RC"
fi

if [ "$RC" -eq 3 ]; then
  echo
  echo " ------------------------------------------------"
  echo "  Данните са свалени успешно, но качването"
  echo "  в GitHub не стана. Проверете settings.ini."
  echo "  Файловете са запазени в тази папка."
  echo " ------------------------------------------------"
  echo
  read -r -p " Enter за изход..." _
  exit 3
fi

echo
echo " Готово. Наличностите са обновени."
echo
read -r -p " Enter за изход..." _

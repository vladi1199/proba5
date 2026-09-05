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

echo
echo " Готово. Файловете са обновени в тази папка."
echo
read -r -p " Да ги кача ли в GitHub? (y/n): " PUB
if [ "$PUB" = "y" ] || [ "$PUB" = "Y" ]; then
  git add results_filstar.csv filstar_xml_*.xml not_found_filstar.csv
  git commit -m "Stock update"
  git push
  echo
  echo " Качено."
fi
echo
read -r -p " Enter за изход..." _

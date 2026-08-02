#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# === Filstar API TEST checker ===
#
# - Без Selenium
# - Без Google
# - Директно през requests
# - Чете SKU от CSV
# - Игнорира коментари между ##
# - Тества:
#       https://filstar.com/search?term=SKU
#       https://filstar.com/api/search?term=SKU
#
# Резултатите се записват в debug_html/


import csv
import os
import time
import requests


# ---------------- ПЪТИЩА ----------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")

DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")

os.makedirs(DEBUG_DIR, exist_ok=True)


# ---------------- НАСТРОЙКИ ----------------

WAIT = 3


URLS = [
    "https://filstar.com/search?term={sku}",
    "https://filstar.com/api/search?term={sku}"
]


HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36",

    "Accept":
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",

    "Accept-Language":
        "bg-BG,bg;q=0.9,en;q=0.8"
}



# ---------------- CSV ЧЕТЕНЕ ----------------

def read_skus(path):

    skus = []

    comment = False

    with open(path, "r", encoding="utf-8-sig") as f:

        for line in f:

            value = line.strip()

            if not value:
                continue


            # пропускаме заглавието
            if value.upper() == "SKU":
                continue


            # начало / край на коментар
            if value == "##":
                comment = not comment
                continue


            # игнорира коментарния блок
            if comment:
                continue


            skus.append(value)


    return skus



# ---------------- SAVE DEBUG ----------------

def save_html(sku, name, html):

    path = os.path.join(
        DEBUG_DIR,
        f"{sku}_{name}.html"
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


    print("🐞 HTML:", path)



# ---------------- TEST ----------------

def check_url(sku, url):

    try:

        print("\n🌐", url)

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )


        print(
            "STATUS:",
            r.status_code,
            "SIZE:",
            len(r.text)
        )


        html = r.text.lower()


        save_html(
            sku,
            "result",
            r.text
        )


        if "just a moment" in html:

            print("⚠️ CLOUDFLARE CHALLENGE")
            return False


        if "950594" in r.text or sku in r.text:

            print("✅ SKU намерен в HTML")
            return True


        if "product" in html:

            print("ℹ️ Има продуктово съдържание")
            return True


        print("❌ Няма очевиден резултат")

        return False


    except Exception as e:

        print(
            "ERROR:",
            e
        )

        return False




# ---------------- MAIN ----------------

def main():

    if not os.path.exists(SKU_CSV):

        print(
            "❌ Липсва:",
            SKU_CSV
        )

        return


    skus = read_skus(SKU_CSV)


    print(
        "🧾 SKU намерени:",
        len(skus)
    )


    for sku in skus:


        print("\n====================")
        print("➡️ SKU:", sku)
        print("====================")


        found = False


        for template in URLS:

            url = template.format(
                sku=sku
            )


            if check_url(
                sku,
                url
            ):

                found = True
                break


            time.sleep(WAIT)



        if not found:

            print(
                "❌ Няма резултат за",
                sku
            )


        time.sleep(WAIT)



if __name__ == "__main__":
    main()

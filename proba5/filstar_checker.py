#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")
RES_CSV = os.path.join(BASE_DIR, "results_filstar.csv")
NF_CSV = os.path.join(BASE_DIR, "not_found_filstar.csv")

DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")
os.makedirs(DEBUG_DIR, exist_ok=True)


BASE_URL = "https://filstar.com"
SEARCH_URL = "https://filstar.com/api/search?term={}"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    ),
    "Accept-Language": "bg-BG,bg;q=0.9"
}


WAIT = 2


session = requests.Session()
session.headers.update(HEADERS)



# ---------------- DEBUG ----------------

def save_debug(sku, html):

    path = os.path.join(
        DEBUG_DIR,
        f"debug_{sku}.html"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(html)

    print("🐞 Debug:", path)



# ---------------- SKU ----------------

def read_skus():

    skus = []

    in_comment = False

    with open(
        SKU_CSV,
        "r",
        encoding="utf-8-sig"
    ) as f:

        for line in f:

            line = line.strip()


            if not line:
                continue


            # заглавен ред
            if line.upper() == "SKU":
                continue


            # начало / край коментар
            if line == "##":

                in_comment = not in_comment
                continue


            if in_comment:
                continue


            skus.append(line)


    return skus



# ---------------- FIND PRODUCT ----------------

def find_product_link(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    links = soup.select(
        ".product-item a[href]"
    )


    print(
        "🔎 product-item линкове:",
        len(links)
    )


    for a in links:

        href = a.get("href")


        if not href:
            continue


        if href.startswith("/"):

            href = urljoin(
                BASE_URL,
                href
            )


        # махаме начална страница
        if href.rstrip("/") == BASE_URL:
            continue


        # махаме api
        if "/api/" in href:
            continue


        print(
            "➡️ Продукт:",
            href
        )


        return href



    return None




# ---------------- PRODUCT DATA ----------------

def extract_product(html, sku):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    text = soup.get_text(
        " ",
        strip=True
    )


    # проверяваме дали SKU е вътре
    if sku not in text:

        print(
            "⚠️ SKU не е намерен в продукта"
        )


    price = None


    # първо търсим евро
    prices = re.findall(
        r"(\d+[.,]\d+)\s*€",
        text
    )


    if prices:

        price = prices[0].replace(
            ",",
            "."
        )


    status = "Наличен"


    if (
        "Изчерпан продукт" in text
        or "Няма наличност" in text
        or "Изчерпан" in text
    ):

        status = "Изчерпан"



    return status, price




# ---------------- PROCESS ----------------

def process_sku(sku):

    print("\n================")
    print("➡️ SKU:", sku)


    url = SEARCH_URL.format(sku)


    print(
        "🌐",
        url
    )


    r = session.get(
        url,
        timeout=30
    )


    print(
        "STATUS:",
        r.status_code,
        "SIZE:",
        len(r.text)
    )


    save_debug(
        sku,
        r.text
    )


    if r.status_code != 200:

        return None



    product_url = find_product_link(
        r.text
    )


    if not product_url:

        print(
            "❌ Няма продукт"
        )

        return None



    time.sleep(WAIT)


    print(
        "🌐 Отварям:",
        product_url
    )


    product = session.get(
        product_url,
        timeout=30
    )


    print(
        "PRODUCT STATUS:",
        product.status_code
    )


    if product.status_code != 200:

        return None



    status, price = extract_product(
        product.text,
        sku
    )


    if price:

        print(
            "✅",
            sku,
            status,
            price
        )


        return [
            sku,
            status,
            "-",
            price
        ]


    print(
        "❌ Няма цена"
    )


    return None




# ---------------- MAIN ----------------

def main():

    skus = read_skus()


    print(
        "🧾 SKU:",
        len(skus)
    )



    with open(
        RES_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(
            [
                "SKU",
                "Наличност",
                "Бройки",
                "Цена (€)"
            ]
        )



    with open(
        NF_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(
            ["SKU"]
        )



    for sku in skus:


        result = process_sku(
            sku
        )


        if result:

            with open(
                RES_CSV,
                "a",
                newline="",
                encoding="utf-8"
            ) as f:

                csv.writer(f).writerow(
                    result
                )


        else:

            with open(
                NF_CSV,
                "a",
                newline="",
                encoding="utf-8"
            ) as f:

                csv.writer(f).writerow(
                    [sku]
                )


        time.sleep(WAIT)




if __name__ == "__main__":
    main()

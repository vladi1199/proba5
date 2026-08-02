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
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36",

    "Accept-Language":
        "bg-BG,bg;q=0.9"
}


WAIT = 2


session = requests.Session()
session.headers.update(HEADERS)



# ==================================================
# DEBUG
# ==================================================

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


    print(
        "🐞 Debug:",
        path
    )



# ==================================================
# SKU READER
# ==================================================

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


            if line.upper() == "SKU":
                continue


            if line == "##":

                in_comment = not in_comment
                continue


            if in_comment:
                continue


            skus.append(line)


    return skus




# ==================================================
# FIND PRODUCT LINK
# ==================================================

def find_product_link(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    # вариант 1
    links = soup.select(
        ".product-image a[href]"
    )


    print(
        "🔎 product-image линкове:",
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


        if href.rstrip("/") == BASE_URL:
            continue


        if "/api/" in href:
            continue


        print(
            "➡️ Продукт:",
            href
        )


        return href




    # вариант 2 - търсим всички линкове

    print(
        "🔎 Резервно търсене..."
    )


    for a in soup.find_all(
        "a",
        href=True
    ):


        href = a["href"]


        if href.startswith("/"):

            href = urljoin(
                BASE_URL,
                href
            )


        if (
            href.startswith(BASE_URL)
            and href.rstrip("/") != BASE_URL
            and "/api/" not in href
        ):

            print(
                "➡️ Резервен продукт:",
                href
            )

            return href



    return None




# ==================================================
# EXTRACT PRODUCT
# ==================================================

def extract_product(html, sku):


    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    text = soup.get_text(
        " ",
        strip=True
    )


    price = None


    # търсим евро цена

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
        or "Изчерпан" in text
        or "Няма наличност" in text
    ):

        status = "Изчерпан"



    return status, price




# ==================================================
# PROCESS SKU
# ==================================================

def process_sku(sku):


    print("\n================")
    print(
        "➡️ SKU:",
        sku
    )


    search_url = SEARCH_URL.format(
        sku
    )


    print(
        "🌐",
        search_url
    )


    r = session.get(
        search_url,
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




# ==================================================
# MAIN
# ==================================================

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
            [
                "SKU"
            ]
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
                    [
                        sku
                    ]
                )


        time.sleep(WAIT)




if __name__ == "__main__":

    main()

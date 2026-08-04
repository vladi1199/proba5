#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import requests

from urllib.parse import urljoin

from playwright.sync_api import sync_playwright



# ================= PATHS =================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


SKU_CSV = os.path.join(
    BASE_DIR,
    "sku_list_filstar.csv"
)


RESULT_CSV = os.path.join(
    BASE_DIR,
    "results_filstar.csv"
)


NOT_FOUND_CSV = os.path.join(
    BASE_DIR,
    "not_found_filstar.csv"
)


DEBUG_DIR = os.path.join(
    BASE_DIR,
    "debug_html"
)


os.makedirs(
    DEBUG_DIR,
    exist_ok=True
)



# ================= SETTINGS =================

BASE_URL = "https://filstar.com"

SEARCH_URL = (
    "https://filstar.com/api/search?term={}"
)


WAIT_TIME = 1




# ================= DEBUG =================


def save_debug(filename, content):

    path = os.path.join(
        DEBUG_DIR,
        filename
    )


    try:

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(content)


        print(
            f"🐞 Debug: {path}"
        )


    except Exception:

        pass




# ================= CSV =================


def read_skus():

    skus = []

    comment_block = False


    with open(
        SKU_CSV,
        "r",
        encoding="utf-8-sig"
    ) as file:


        for line in file:


            value = line.strip()


            if not value:

                continue



            if value.upper() == "SKU":

                continue



            if value == "##":

                comment_block = not comment_block

                continue



            if comment_block:

                continue



            skus.append(value)



    return skus




def init_csv():


    with open(
        RESULT_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:


        writer = csv.writer(file)


        writer.writerow(
            [
                "SKU",
                "Наличност",
                "Бройки",
                "Цена"
            ]
        )



    with open(
        NOT_FOUND_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:


        writer = csv.writer(file)


        writer.writerow(
            [
                "SKU"
            ]
        )





def save_result(row):


    with open(
        RESULT_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:


        csv.writer(file).writerow(
            row
        )




def save_not_found(sku):


    with open(
        NOT_FOUND_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:


        csv.writer(file).writerow(
            [
                sku
            ]
        )




# ================= SEARCH =================


def find_product_link(sku):


    url = SEARCH_URL.format(
        sku
    )


    print(
        f"🌐 {url}"
    )


    response = requests.get(
        url,
        headers={
            "User-Agent":
            "Mozilla/5.0"
        },
        timeout=30
    )


    print(
        f"STATUS: {response.status_code} SIZE: {len(response.text)}"
    )


    save_debug(
        f"search_{sku}.html",
        response.text
    )



    if response.status_code != 200:

        return None



    links = re.findall(
        r'<a href="([^"]+)"\s+class="product-name"',
        response.text
    )



    products = []



    for link in links:


        full_url = urljoin(
            BASE_URL,
            link
        )


        if full_url not in products:

            products.append(full_url)




    print(
        f"🔎 Намерени продукти: {len(products)}"
    )



    if products:

        return products[0]



    return None
    # ================= PRODUCT PAGE =================


def open_product(page, url):


    print(
        f"➡️ PRODUCT: {url}"
    )


    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=30000
    )


    time.sleep(
        WAIT_TIME
    )





# ================= EXTRACT PRODUCT =================


def extract_product(page, sku):

    html = page.content()


    save_debug(
        f"product_{sku}.html",
        html
    )


    print(
        "🔎 Проверявам HTML за цена..."
    )


    euro_prices = re.findall(
        r"\d+[.,]?\d*\s*€",
        html
    )


    leva_prices = re.findall(
        r"\d+[.,]?\d*\s*лв",
        html
    )


    print(
        f"💶 Евро намерени: {euro_prices[:10]}"
    )


    print(
        f"💰 Лева намерени: {leva_prices[:10]}"
    )


    price = None


    if euro_prices:

        price = (
            re.search(
                r"\d+[.,]?\d*",
                euro_prices[0]
            )
            .group()
            .replace(",", ".")
        )


    elif leva_prices:

        price = (
            re.search(
                r"\d+[.,]?\d*",
                leva_prices[0]
            )
            .group()
            .replace(",", ".")
        )



    if price:

        print(
            f"✅ Намерена цена: {price}"
        )

        return (
            "Наличен",
            "-",
            price
        )


    print(
        "❌ Няма цена в HTML"
    )


    return (
        "Неизвестно",
        "-",
        None
    )
    # ================= MAIN =================


def main():


    init_csv()



    skus = read_skus()



    print(
        f"🧾 Общо SKU: {len(skus)}"
    )



    with sync_playwright() as p:



        browser = p.chromium.launch(
            headless=True
        )



        context = browser.new_context(
            user_agent=
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/120 Safari/537.36"
        )



        page = context.new_page()



        for sku in skus:



            print("================")

            print(
                f"➡️ SKU: {sku}"
            )



            product_url = find_product_link(
                sku
            )



            if not product_url:



                print(
                    "❌ Няма намерен продукт"
                )


                save_not_found(
                    sku
                )


                continue



            try:



                open_product(
                    page,
                    product_url
                )



                status, qty, price = extract_product(
                    page,
                    sku
                )



                if price:



                    print(
                        f"✅ {price} | {status}"
                    )



                    save_result(
                        [
                            sku,
                            status,
                            qty,
                            price
                        ]
                    )



                else:



                    print(
                        "❌ Няма цена"
                    )



                    save_not_found(
                        sku
                    )



            except Exception as e:



                print(
                    f"❌ Грешка при {sku}: {e}"
                )


                save_not_found(
                    sku
                )



            time.sleep(
                WAIT_TIME
            )



        browser.close()



    print(
        "✅ Готово"
    )





if __name__ == "__main__":

    main()

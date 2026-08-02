#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import requests

from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ================= PATHS =================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")
RES_CSV = os.path.join(BASE_DIR, "results_filstar.csv")
NF_CSV = os.path.join(BASE_DIR, "not_found_filstar.csv")

DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")

os.makedirs(DEBUG_DIR, exist_ok=True)


BASE_URL = "https://filstar.com"
SEARCH_URL = "https://filstar.com/api/search?term={}"


WAIT = 3



# ================= DEBUG =================


def save_debug(filename, html):

    try:
        path = os.path.join(DEBUG_DIR, filename)

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"🐞 Debug: {path}")

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
    ) as f:


        for line in f:


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



def init_files():

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
                "Цена (лв.)"
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



def save_result(row):

    with open(
        RES_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(row)



def save_not_found(sku):

    with open(
        NF_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow([sku])




# ================= SEARCH =================


def find_product_link(sku):


    url = SEARCH_URL.format(sku)


    print(
        f"🌐 {url}"
    )


    r = requests.get(
        url,
        headers={
            "User-Agent":
            "Mozilla/5.0"
        },
        timeout=30
    )


    print(
        f"STATUS: {r.status_code} SIZE: {len(r.text)}"
    )


    save_debug(
        f"search_{sku}.html",
        r.text
    )


    if r.status_code != 200:
        return None



    links = re.findall(
        r'href="([^"]+)"',
        r.text
    )



    exclude = [

        "manifest.json",

        "/build/",
        "/css/",
        "/js/",
        "/images/",

        "/brands/",
        "/category/",
        "/categories/",

        "/search",
        "/api/",

        ".css",
        ".js",
        ".png",
        ".jpg",
        ".svg",
        ".ico"

    ]



    products = []



    for link in links:


        if not link.startswith("/"):

            continue



        if any(
            x in link
            for x in exclude
        ):

            continue



        full = urljoin(
            BASE_URL,
            link
        )



        if full not in products:

            products.append(full)



    print(
        f"🔎 Продуктови линкове: {len(products)}"
    )



    if products:

        return products[0]



    return None





# ================= PRODUCT =================


def extract_product(page, sku):


    html = page.content()



    save_debug(
        f"product_{sku}.html",
        html
    )



    # цена

    prices = re.findall(

        r'(\d+[.,]?\d*)\s*(?:лв\.|€)',

        html

    )


    price = None


    if prices:

        price = prices[0].replace(",", ".")



    status = "Наличен"



    if (

        "Изчерпан продукт" in html

        or

        "send-request" in html

    ):

        status = "Изчерпан"



    return (
        status,
        "-",
        price
    )






# ================= MAIN =================


def main():


    init_files()


    skus = read_skus()



    print(
        f"🧾 SKU: {len(skus)}"
    )



    with sync_playwright() as p:


        browser = p.chromium.launch(
            headless=True
        )



        page = browser.new_page(
            user_agent=

            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/120 Safari/537.36"

        )



        for sku in skus:



            print("================")

            print(
                f"➡️ SKU: {sku}"
            )



            product = find_product_link(sku)



            if not product:


                print(
                    "❌ Няма продукт"
                )


                save_not_found(sku)

                continue




            print(
                f"➡️ PRODUCT: {product}"
            )



            try:


                page.goto(

                    product,

                    wait_until="domcontentloaded",

                    timeout=60000

                )



                time.sleep(WAIT)



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
                        "❌ няма цена"
                    )

                    save_not_found(sku)




            except PlaywrightTimeoutError:


                print(
                    "⏱ Timeout"
                )


                save_not_found(sku)



            except Exception as e:


                print(
                    f"ERROR: {e}"
                )


                save_not_found(sku)




        browser.close()



    print(
        "✅ Готово"
    )




if __name__ == "__main__":

    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import requests

from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


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


def save_debug(filename, content):

    try:
        path = os.path.join(DEBUG_DIR, filename)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"🐞 Debug: {path}")

    except:
        pass



# ================= CSV =================


def read_skus():

    result = []

    comment = False


    with open(
        SKU_CSV,
        "r",
        encoding="utf-8-sig"
    ) as f:


        for line in f:

            sku = line.strip()


            if not sku:
                continue


            if sku.upper() == "SKU":
                continue


            if sku == "##":

                comment = not comment
                continue


            if comment:
                continue


            result.append(sku)



    return result




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



def save_nf(sku):

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



    # Само продуктови линкове
    links = re.findall(
        r'<a href="([^"]+)"\s+class="product-name"',
        r.text
    )


    products = []


    for link in links:


        full = urljoin(
            BASE_URL,
            link
        )


        if full not in products:

            products.append(full)



    print(
        f"🔎 Намерени продукти: {len(products)}"
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



    price = None



    # първо търсим евро
    m = re.search(
        r'(\d+[.,]?\d*)\s*€',
        html
    )


    if m:

        price = m.group(1).replace(",", ".")



    else:


        m = re.search(
            r'(\d+[.,]?\d*)\s*лв\.',
            html
        )


        if m:

            price = m.group(1).replace(",", ".")



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

                save_nf(sku)

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

                    save_nf(sku)



            except PlaywrightTimeoutError:


                print(
                    "⏱ Timeout"
                )

                save_nf(sku)



            except Exception as e:


                print(
                    f"ERROR: {e}"
                )

                save_nf(sku)




        browser.close()



    print(
        "✅ Готово"
    )



if __name__ == "__main__":
    main()

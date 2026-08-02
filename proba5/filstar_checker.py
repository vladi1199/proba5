#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time

from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ================= PATHS =================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")
RES_CSV = os.path.join(BASE_DIR, "results_filstar.csv")
NF_CSV = os.path.join(BASE_DIR, "not_found_filstar.csv")

DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")

os.makedirs(DEBUG_DIR, exist_ok=True)



# ================= SETTINGS =================

BASE_URL = "https://filstar.com"

SEARCH_URL = (
    "https://filstar.com/api/search?term={}"
)

WAIT_TIME = 3



# ================= DEBUG =================

def save_debug(filename, content):

    try:

        path = os.path.join(
            DEBUG_DIR,
            filename
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(content)


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
    ) as f:


        for line in f:

            value = line.strip()


            if not value:

                continue



            # заглавен ред

            if value.upper() == "SKU":

                continue



            # начало / край коментари

            if value == "##":

                comment_block = not comment_block

                continue



            # игнорирай коментари

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

        csv.writer(f).writerow(
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



    import requests


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




    # само реални продуктови линкове

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
# ================= PRODUCT EXTRACTION =================


def extract_product(page, sku):


    html = page.content()


    save_debug(
        f"product_{sku}.html",
        html
    )


    price = None

    status = "Наличен"



    try:


        print(
            "⏳ Чакам fast-order-table..."
        )


        page.wait_for_selector(
            "#fast-order-table tbody tr",
            timeout=20000
        )



        rows = page.locator(
            "#fast-order-table tbody tr"
        )



        count = rows.count()



        print(
            f"🔎 Варианти: {count}"
        )



        for i in range(count):


            row = rows.nth(i)



            text = row.inner_text()



            print(
                f"ROW {i}: {text[:120]}"
            )



            # точно SKU

            if re.search(
                rf"\b{re.escape(str(sku))}\b",
                text
            ):



                print(
                    f"✅ Намерен SKU ред: {text}"
                )



                row_html = row.inner_html()



                # наличност


                if (
                    "Изчерпан продукт" in text
                    or
                    "send-request" in row_html
                ):

                    status = "Изчерпан"



                # първо нормална цена в €

                euro = re.search(
                    r"(\d+[.,]?\d*)\s*€",
                    text
                )


                if euro:

                    price = (
                        euro.group(1)
                        .replace(",", ".")
                    )



                else:


                    lev = re.search(
                        r"(\d+[.,]?\d*)\s*лв",
                        text
                    )


                    if lev:

                        price = (
                            lev.group(1)
                            .replace(",", ".")
                        )



                break




    except Exception as e:


        print(
            f"⚠️ Няма fast-order-table: {e}"
        )



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



            product = find_product_link(
                sku
            )



            if not product:


                print(
                    "❌ Няма продукт"
                )

                save_not_found(
                    sku
                )

                continue




            print(
                f"➡️ PRODUCT: {product}"
            )



            try:



                page.goto(
                    product,
                    wait_until="networkidle",
                    timeout=60000
                )



                time.sleep(
                    WAIT_TIME
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
                        "❌ няма цена"
                    )

                    save_not_found(
                        sku
                    )



            except PlaywrightTimeoutError:


                print(
                    "⏱ Timeout"
                )

                save_not_found(
                    sku
                )



            except Exception as e:


                print(
                    f"❌ ERROR: {e}"
                )

                save_not_found(
                    sku
                )




        browser.close()



    print(
        "✅ Готово"
    )




if __name__ == "__main__":

    main()


    return None

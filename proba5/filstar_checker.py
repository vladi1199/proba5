#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")
RES_CSV = os.path.join(BASE_DIR, "results_filstar.csv")
NF_CSV = os.path.join(BASE_DIR, "not_found_filstar.csv")
DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")

os.makedirs(DEBUG_DIR, exist_ok=True)

SEARCH_URL = "https://filstar.com/search?term={}"


WAIT = 5


def save_debug(page, sku, name):
    try:
        path = os.path.join(
            DEBUG_DIR,
            f"debug_{sku}_{name}.html"
        )

        with open(path, "w", encoding="utf-8") as f:
            f.write(page.content())

        print("🐞 Debug:", path)

    except Exception:
        pass



def init_files():

    with open(RES_CSV, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            ["SKU", "Наличност", "Бройки", "Цена"]
        )

    with open(NF_CSV, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            ["SKU"]
        )



def append_result(row):

    with open(
        RES_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:
        csv.writer(f).writerow(row)



def append_nf(sku):

    with open(
        NF_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:
        csv.writer(f).writerow([sku])



def read_skus():

    result = []

    with open(
        SKU_CSV,
        encoding="utf-8-sig"
    ) as f:

        for line in f:

            sku = line.strip()

            if not sku:
                continue

            if sku.upper() == "SKU":
                continue

            result.append(sku)

    return result



def only_digits(x):

    return re.sub(
        r"\D+",
        "",
        x or ""
    )



def cloudflare_detected(page):

    title = page.title()

    text = page.content()

    if "Just a moment" in title:
        return True

    if "Performing security verification" in text:
        return True

    return False



def find_product(page, sku):

    links = page.locator(
        "a"
    )

    count = links.count()

    result = []

    for i in range(count):

        try:

            href = links.nth(i).get_attribute("href")

            if href and "/product/" in href:

                if href not in result:
                    result.append(href)

        except:
            pass


    return result[:10]



def parse_product(page, sku):

    try:

        table = page.locator(
            "#fast-order-table tbody tr"
        )

        rows = table.count()


        for i in range(rows):

            row = table.nth(i)

            txt = row.inner_text()


            if sku in txt:

                price = None


                m = re.search(
                    r"(\d+[.,]?\d*)\s*лв",
                    txt
                )


                if m:
                    price = (
                        m.group(1)
                        .replace(",", ".")
                    )


                status = "Наличен"


                if "Изчерпан" in txt:
                    status = "Изчерпан"


                return (
                    status,
                    "-",
                    price
                )


    except Exception:
        pass


    return None, None, None



def process(page, sku):

    print(
        "➡️ SKU:",
        sku
    )

    url = SEARCH_URL.format(sku)

    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )

    time.sleep(WAIT)


    if cloudflare_detected(page):

        print(
            "⚠️ Cloudflare challenge"
        )

        save_debug(
            page,
            sku,
            "cloudflare"
        )

        append_nf(sku)

        return


    products = find_product(
        page,
        sku
    )


    if not products:

        save_debug(
            page,
            sku,
            "no_products"
        )

        append_nf(sku)

        return



    for link in products:

        try:

            page.goto(
                link,
                wait_until="domcontentloaded",
                timeout=60000
            )

            time.sleep(WAIT)


            status, qty, price = parse_product(
                page,
                sku
            )


            if price:

                append_result(
                    [
                        sku,
                        status,
                        qty,
                        price
                    ]
                )

                print(
                    "✅",
                    sku,
                    price
                )

                return


        except Exception:
            continue


    append_nf(sku)



def main():

    init_files()

    skus = read_skus()

    print(
        "SKU:",
        len(skus)
    )


    with sync_playwright() as p:


        browser = p.chromium.launch(
            headless=True
        )


        page = browser.new_page(
            viewport={
                "width":1280,
                "height":2000
            },
            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "Chrome/120 Safari/537.36"
            )
        )


        for sku in skus:

            process(
                page,
                sku
            )

            time.sleep(3)


        browser.close()



if __name__ == "__main__":
    main()

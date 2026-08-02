#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import requests
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


# ---------------- ПЪТИЩА ----------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")
RES_CSV = os.path.join(BASE_DIR, "results_filstar.csv")
NF_CSV = os.path.join(BASE_DIR, "not_found_filstar.csv")

DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")
os.makedirs(DEBUG_DIR, exist_ok=True)


# ---------------- НАСТРОЙКИ ----------------

BETWEEN_SKU = 4
PAGE_TIMEOUT = 40


# ---------------- DRIVER ----------------


def create_driver():

    opts = Options()

    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,2000")

    opts.add_argument(
        "--user-agent="
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        " AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )

    driver = webdriver.Chrome(options=opts)

    driver.set_page_load_timeout(PAGE_TIMEOUT)

    return driver



# ---------------- HELPERS ----------------


def only_digits(s):

    return re.sub(r"\D+", "", s or "")



def save_debug(driver, sku, name):

    try:

        path = os.path.join(
            DEBUG_DIR,
            f"debug_{sku}_{name}.html"
        )

        with open(path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        print("🐞 Debug:", path)

    except:
        pass



def read_skus():

    result=[]

    with open(
        SKU_CSV,
        "r",
        encoding="utf-8-sig"
    ) as f:

        for row in f:

            row=row.strip()

            if not row:
                continue

            if row.upper()=="SKU":
                continue

            result.append(row)

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
                "Цена"
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



def append_result(row):

    with open(
        RES_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(row)



def append_not_found(sku):

    with open(
        NF_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow([sku])



# ---------------- GOOGLE SEARCH ----------------


def google_search(driver, sku):

    query = f"site:filstar.com {sku}"

    url = (
        "https://www.google.com/search?q="
        + query.replace(" ","+")
    )


    print("🔎 Google:", query)


    driver.get(url)

    time.sleep(3)


    links=[]


    soup = BeautifulSoup(
        driver.page_source,
        "html.parser"
    )


    for a in soup.find_all("a"):

        href=a.get("href")

        if not href:
            continue


        if "filstar.com" in href:

            if href.startswith("/url?q="):

                href=href.split("/url?q=")[1].split("&")[0]


            links.append(href)



    clean=[]

    for x in links:

        if x not in clean:
            clean.append(x)


    return clean[:10]



# ---------------- PRODUCT CHECK ----------------


def extract_product(driver, sku):

    html = driver.page_source


    if (
        "Just a moment" in html
        or "Cloudflare" in html
    ):

        return None


    soup=BeautifulSoup(
        html,
        "html.parser"
    )


    text=soup.get_text(
        " ",
        strip=True
    )


    if str(sku) not in text:
        return None



    price=None


    m=re.search(
        r"(\d+[.,]?\d*)\s*€",
        text
    )

    if m:

        price=m.group(1).replace(",", ".")



    if not price:

        m=re.search(
            r"(\d+[.,]?\d*)\s*лв",
            text
        )

        if m:

            price=m.group(1).replace(",", ".")



    status="Наличен"


    if (
        "Изчерпан продукт" in text
        or "Няма наличност" in text
    ):

        status="Изчерпан"



    return [
        sku,
        status,
        "-",
        price or "-"
    ]



# ---------------- PROCESS ----------------


def process(driver, sku):


    print("\n➡️ SKU:", sku)


    links=google_search(
        driver,
        sku
    )


    if not links:

        print("❌ няма Google резултат")

        append_not_found(sku)

        return



    for link in links:


        try:

            print("🌐", link)


            driver.get(link)

            time.sleep(3)


            result=extract_product(
                driver,
                sku
            )


            if result:

                print(
                    "✅ намерен:",
                    result
                )

                append_result(result)

                return



        except Exception as e:

            continue



    save_debug(
        driver,
        sku,
        "failed"
    )


    append_not_found(sku)



# ---------------- MAIN ----------------


def main():


    init_files()


    skus=read_skus()


    print(
        "🧾 SKU:",
        len(skus)
    )


    driver=create_driver()


    try:


        for sku in skus:

            process(
                driver,
                sku
            )

            time.sleep(
                BETWEEN_SKU
            )


    finally:

        driver.quit()



    print("✅ Готово")



if __name__=="__main__":

    main()

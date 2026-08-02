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

API_SEARCH = "https://filstar.com/api/search?term={}"


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



def save_debug(sku, html):
    path = os.path.join(
        DEBUG_DIR,
        f"debug_{sku}.html"
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    print("🐞 Debug:", path)



def read_skus():

    skus = []

    comment = False

    with open(SKU_CSV, "r", encoding="utf-8-sig") as f:

        for line in f:

            line=line.strip()

            if not line:
                continue


            if line.upper()=="SKU":
                continue


            if line=="##":
                comment = not comment
                continue


            if comment:
                continue


            skus.append(line)


    return skus



def find_product_link(html, sku):

    soup = BeautifulSoup(html,"html.parser")


    links=[]


    for a in soup.find_all("a", href=True):

        href=a["href"]

        if href.startswith("/"):

            href=urljoin(BASE_URL,href)


        links.append(href)



    # махаме дубли
    links=list(dict.fromkeys(links))


    for link in links:

        if link.startswith(BASE_URL):

            if "/api/" not in link:

                return link


    return None



def extract_product(driver_html, sku):

    soup=BeautifulSoup(driver_html,"html.parser")


    text=soup.get_text(" ",strip=True)



    price=None


    # търси евро
    m=re.search(
        r"(\d+[.,]\d+)\s*€",
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



    return status, price




def process_sku(sku):

    print("\n================")
    print("➡️ SKU:",sku)


    url=API_SEARCH.format(sku)


    print("🌐",url)


    r=session.get(url,timeout=30)


    print(
        "STATUS:",
        r.status_code,
        "SIZE:",
        len(r.text)
    )


    save_debug(sku,r.text)



    if r.status_code!=200:

        print("❌ Грешка")
        return None



    product=find_product_link(
        r.text,
        sku
    )


    if not product:

        print("❌ Няма продукт")
        return None



    print("✅ PRODUCT:")
    print(product)



    time.sleep(WAIT)



    p=session.get(
        product,
        timeout=30
    )


    if p.status_code!=200:

        print("❌ Не може да отвори продукта")
        return None



    status,price=extract_product(
        p.text,
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



    print("❌ Няма цена")

    return None




def main():

    skus=read_skus()


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


        result=process_sku(sku)



        if result:

            with open(
                RES_CSV,
                "a",
                newline="",
                encoding="utf-8"
            ) as f:

                csv.writer(f).writerow(result)


        else:

            with open(
                NF_CSV,
                "a",
                newline="",
                encoding="utf-8"
            ) as f:

                csv.writer(f).writerow([sku])


        time.sleep(WAIT)




if __name__=="__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ================= ПЪТИЩА =================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")
RES_CSV = os.path.join(BASE_DIR, "results_filstar.csv")
NF_CSV = os.path.join(BASE_DIR, "not_found_filstar.csv")

DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")

os.makedirs(DEBUG_DIR, exist_ok=True)


# ================= НАСТРОЙКИ =================

API_URL = "https://filstar.com/api/search?term={}"

WAIT = 3


HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/120 Safari/537.36",

    "Accept-Language": "bg-BG,bg;q=0.9"
}


# ================= CSV =================

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
                "Цена (лв.)",
                "URL"
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



# ================= SKU =================


def read_skus():

    skus=[]

    comment=False


    with open(
        SKU_CSV,
        encoding="utf-8-sig"
    ) as f:


        for line in f:

            v=line.strip()


            if not v:
                continue


            if v.upper()=="SKU":
                continue


            if v=="##":

                comment=not comment
                continue


            if comment:
                continue


            skus.append(v)



    return skus



# ================= DEBUG =================


def save_debug(name,html):

    path=os.path.join(
        DEBUG_DIR,
        name
    )


    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(html)


    print("🐞 Debug:",path)



# ================= PARSE =================


def get_product_from_api(sku):


    url=API_URL.format(sku)


    print("🌐",url)


    r=requests.get(
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


    save_debug(
        f"debug_{sku}.html",
        r.text
    )


    if r.status_code != 200:

        return None



    soup=BeautifulSoup(
        r.text,
        "html.parser"
    )


    # намиране на продукт


    links=[]


    for a in soup.select(
        ".product-image a"
    ):

        href=a.get("href")


        if href:

            links.append(
                urljoin(
                    "https://filstar.com",
                    href
                )
            )


    if not links:


        for a in soup.find_all("a",href=True):

            href=a["href"]


            if href.startswith("/"):

                links.append(
                    urljoin(
                        "https://filstar.com",
                        href
                    )
                )



    links=list(dict.fromkeys(links))


    print(
        "🔎 намерени линкове:",
        len(links)
    )


    if not links:

        return None



    product_url=links[0]


    print(
        "➡️ PRODUCT:",
        product_url
    )


    text=soup.get_text(
        " ",
        strip=True
    )


    # проверка SKU

    if sku not in text:

        print(
            "⚠️ SKU не е в текста"
        )



    # =====================
    # Цена
    # =====================


    price=None


    price_match=re.search(
        r"(\d+[.,]\d+)\s*лв",
        text
    )


    if price_match:

        price=price_match.group(1).replace(",", ".")



    # =====================
    # Наличност
    # =====================


    status="Наличен"


    if (
        "Изчерпан продукт" in text
        or
        "Няма наличност" in text
    ):

        status="Изчерпан"



    return {

        "url":product_url,
        "price":price,
        "status":status

    }




# ================= MAIN =================


def main():

    init_files()


    skus=read_skus()


    print(
        "🧾 SKU:",
        len(skus)
    )



    for sku in skus:


        print("\n================")
        print("➡️ SKU:",sku)


        try:


            result=get_product_from_api(
                sku
            )


            if result and result["price"]:


                print(
                    "✅",
                    result["price"],
                    result["status"]
                )


                append_result(
                    [
                        sku,
                        result["status"],
                        "-",
                        result["price"],
                        result["url"]
                    ]
                )


            else:

                print(
                    "❌ Няма данни"
                )

                append_nf(
                    sku
                )


        except Exception as e:

            print(
                "ERROR:",
                e
            )

            append_nf(
                sku
            )


        time.sleep(WAIT)



    print("\n✅ Готово")



if __name__=="__main__":

    main()

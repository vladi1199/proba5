#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import json

from playwright.sync_api import sync_playwright


# ================= PATHS =================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")

RESULT_CSV = os.path.join(BASE_DIR, "results_filstar.csv")

NOT_FOUND_CSV = os.path.join(BASE_DIR, "not_found_filstar.csv")

DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")

os.makedirs(DEBUG_DIR, exist_ok=True)


# ================= SETTINGS =================

BASE_URL = "https://filstar.com"

WAIT = 2



# ================= DEBUG =================


def save_debug(name, content):

    path = os.path.join(DEBUG_DIR, name)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print("🐞 Debug:", name)



# ================= CSV =================


def read_skus():

    result = []

    comment = False

    with open(
        SKU_CSV,
        encoding="utf-8-sig"
    ) as f:

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


            result.append(line)


    return result




def init_csv():

    with open(
        RESULT_CSV,
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
        NOT_FOUND_CSV,
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
        RESULT_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(row)





def save_not_found(sku):

    with open(
        NOT_FOUND_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(
            [sku]
        )





# ================= SEARCH =================


def search_product(page, sku):


    url=f"https://filstar.com/api/search?term={sku}"


    print(
        "🌐 SEARCH:",
        url
    )


    html = page.evaluate(
        """
        async (url)=>{

            let r = await fetch(url,{
                credentials:"include",
                headers:{
                    "X-Requested-With":"XMLHttpRequest"
                }
            });

            return await r.text();
        }

        """,
        url
    )



    save_debug(
        f"search_{sku}.html",
        html
    )


    ids = re.findall(
        r'/get-serialize-product/(\d+)',
        html
    )


    ids=list(dict.fromkeys(ids))


    print(
        "ID кандидати:",
        ids
    )


    if ids:

        return ids[0]


    return None




# ================= JSON =================


def get_product_json(page, product_id):


    url=f"/get-serialize-product/{product_id}"


    print(
        "📦 JSON:",
        url
    )


    data = page.evaluate(
        """
        async (url)=>{

            let r = await fetch(url,{
                credentials:"include",
                headers:{
                    "X-Requested-With":"XMLHttpRequest",
                    "Accept":"application/json"
                }
            });


            return {
                status:r.status,
                text:await r.text()
            };

        }

        """,
        url
    )


    print(
        "JSON STATUS:",
        data["status"]
    )


    save_debug(
        f"json_{product_id}.html",
        data["text"]
    )



    if data["status"]!=200:

        return None



    try:

        return json.loads(
            data["text"]
        )


    except Exception:

        return None





# ================= EXTRACT =================


def extract_product(product, sku):


    try:

        variant = product["defaultVariant"]


        price = variant.get(
            "price"
        )


        quantity = variant.get(
            "quantity"
        )


        if quantity and quantity>0:

            status="Наличен"

        else:

            status="Няма наличност"



        print(
            "Цена:",
            price,
            "Количество:",
            quantity
        )


        return (
            status,
            quantity,
            price
        )


    except Exception as e:


        print(
            "EXTRACT ERROR:",
            e
        )


        return None,None,None





# ================= MAIN =================


def main():

    init_csv()


    skus=read_skus()


    print(
        "Общо SKU:",
        len(skus)
    )



    with sync_playwright() as p:


        browser=p.chromium.launch(
            headless=True
        )


        context=browser.new_context(
            user_agent=
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )


        page=context.new_page()


        print(
            "🌐 Отварям Filstar..."
        )


        try:

            page.goto(
                BASE_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

        except:

            pass



        time.sleep(5)



        print(
            "🍪 Cookies:",
            len(
                context.cookies()
            )
        )



        for sku in skus:


            print("================")

            print(
                "➡️ SKU:",
                sku
            )


            try:


                product_id=search_product(
                    page,
                    sku
                )


                if not product_id:

                    print(
                        "❌ Няма продукт"
                    )

                    save_not_found(sku)

                    continue



                print(
                    "✅ Product ID:",
                    product_id
                )


                product=get_product_json(
                    page,
                    product_id
                )


                if not product:


                    print(
                        "❌ Няма JSON"
                    )

                    save_not_found(sku)

                    continue



                status,qty,price=extract_product(
                    product,
                    sku
                )


                if price:


                    save_result(
                        [
                            sku,
                            status,
                            qty,
                            price
                        ]
                    )

                    print(
                        "✅ записан"
                    )


                else:

                    save_not_found(sku)


            except Exception as e:


                print(
                    "ERROR:",
                    e
                )

                save_not_found(sku)



            time.sleep(WAIT)



        browser.close()



    print(
        "✅ Готово"
    )




if __name__=="__main__":

    main()

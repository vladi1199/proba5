import csv
import re
import time

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://filstar.com"
CSV_FILE = "sku_list_filstar.csv"

WAIT = 0


def load_skus():
    skus = []
    skip_block = False

    with open(
        CSV_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            sku = str(
                row.get("SKU", "")
            ).strip()

            if sku == "##":
                skip_block = not skip_block
                continue

            if skip_block:
                continue

            if sku:
                skus.append(sku)

    return skus


def find_product_block(soup, sku):
    """
    Намира продуктовия блок чрез SKU-то,
    което се намира в името на продуктовата снимка.
    """

    images = soup.find_all("img")

    for image in images:

        src = image.get("src", "") or ""
        srcset = image.get("srcset", "") or ""

        image_sources = (
            src + " " + srcset
        )

        if sku in image_sources:

            current = image

            for _ in range(15):

                if current is None:
                    break

                if current.name == "div":

                    classes = current.get(
                        "class",
                        []
                    )

                    if (
                        "product-item-wapper"
                        in classes
                    ):

                        return current

                current = current.parent

    return None


def extract_product_data(
    soup,
    product_block,
    sku
):

    result = {
        "sku": sku,
        "found": True,
        "product_id": "",
        "name": "",
        "price": "",
        "available": "",
        "status": "",
    }

    # ---------------------------------------------------------
    # PRODUCT ID
    # ---------------------------------------------------------

    result["product_id"] = (
        product_block.get(
            "data-product-id",
            ""
        )
    )

    # ---------------------------------------------------------
    # PRODUCT NAME
    # ---------------------------------------------------------

    result["name"] = (
        product_block.get(
            "data-product-name",
            ""
        )
        or
        product_block.get(
            "data-product-variant",
            ""
        )
    ).strip()

    # ---------------------------------------------------------
    # ЦЕЛИЯТ ТЕКСТ НА ПРОДУКТА
    # ---------------------------------------------------------

    block_text = product_block.get_text(
        " ",
        strip=True
    )

    # ---------------------------------------------------------
    # ЦЕНА В EUR
    # ---------------------------------------------------------

    price = ""

    price_patterns = [
        r"(\d+[.,]\d{2})\s*€",
        r"/\s*(\d+[.,]\d{2})\s*€",
    ]

    for pattern in price_patterns:

        match = re.search(
            pattern,
            block_text,
            re.IGNORECASE
        )

        if match:

            price = (
                match.group(1)
                .replace(",", ".")
            )

            break

    result["price"] = price

    # ---------------------------------------------------------
    # НАЛИЧНОСТ
    # ---------------------------------------------------------

    classes = product_block.get(
        "class",
        []
    )

    class_text = " ".join(
        classes
    ).lower()

    text_lower = block_text.lower()

    # Важно:
    # първо проверяваме класа на продуктовия блок,
    # защото Filstar използва:
    #
    # product-list-view out-of-stock
    #

    if "out-of-stock" in class_text:
        result["available"] = "NO"
        result["status"] = "OUT_OF_STOCK"

    elif "out of stock" in class_text:
        result["available"] = "NO"
        result["status"] = "OUT_OF_STOCK"

    elif "няма наличност" in text_lower:
        result["available"] = "NO"
        result["status"] = "OUT_OF_STOCK"

    elif "неналичен" in text_lower:
        result["available"] = "NO"
        result["status"] = "OUT_OF_STOCK"

    elif "изчерпан" in text_lower:
        result["available"] = "NO"
        result["status"] = "OUT_OF_STOCK"

    elif "в наличност" in text_lower:
        result["available"] = "YES"
        result["status"] = "AVAILABLE"

    elif "наличен" in text_lower:
        result["available"] = "YES"
        result["status"] = "AVAILABLE"

    else:
        result["available"] = "UNKNOWN"
        result["status"] = "NO_STOCK_MARKER"

    return result


def check_sku(
    session,
    sku
):

    url = f"{BASE_URL}/api/search"

    print()
    print("=" * 70)
    print(f"SKU: {sku}")
    print("=" * 70)

    try:

        response = session.get(
            url,
            params={
                "term": sku
            },
            timeout=30
        )

        print(
            f"HTTP: {response.status_code}"
        )

        if response.status_code != 200:

            return {
                "sku": sku,
                "found": False,
                "product_id": "",
                "name": "",
                "price": "",
                "available": "",
                "status": (
                    f"HTTP_{response.status_code}"
                ),
            }

        html = response.text

        print(
            f"HTML: {len(html)} characters"
        )

        # -----------------------------------------------------
        # Проверяваме колко пъти SKU-то присъства
        # -----------------------------------------------------

        sku_count = html.count(sku)

        print(
            f"SKU occurrences: {sku_count}"
        )

        if sku_count == 0:

            print(
                "❌ SKU не е намерено в HTML."
            )

            return {
                "sku": sku,
                "found": False,
                "product_id": "",
                "name": "",
                "price": "",
                "available": "",
                "status": "SKU_NOT_FOUND",
            }

        # -----------------------------------------------------
        # BeautifulSoup
        # -----------------------------------------------------

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        # -----------------------------------------------------
        # Намираме продуктовия блок
        # чрез SKU в image filename
        # -----------------------------------------------------

        product_block = find_product_block(
            soup,
            sku
        )

        if product_block is None:

            print(
                "❌ Не е намерен продуктов блок "
                "чрез image filename."
            )

            return {
                "sku": sku,
                "found": True,
                "product_id": "",
                "name": "",
                "price": "",
                "available": "",
                "status": (
                    "SKU_FOUND_PRODUCT_BLOCK_NOT_FOUND"
                ),
            }

        # -----------------------------------------------------
        # Извличаме данните
        # -----------------------------------------------------

        result = extract_product_data(
            soup,
            product_block,
            sku
        )

        # -----------------------------------------------------
        # Debug информация
        # -----------------------------------------------------

        print()
        print(
            f"Product ID: "
            f"{result['product_id']}"
        )

        print(
            f"Name: "
            f"{result['name']}"
        )

        print(
            f"Price: "
            f"{result['price']} €"
        )

        print(
            f"Available: "
            f"{result['available']}"
        )

        print(
            f"Status: "
            f"{result['status']}"
        )

        # -----------------------------------------------------
        # Показваме и image source-а,
        # чрез който е намерен SKU
        # -----------------------------------------------------

        images = product_block.find_all(
            "img"
        )

        for image in images:

            src = image.get(
                "src",
                ""
            )

            srcset = image.get(
                "srcset",
                ""
            )

            if sku in src or sku in srcset:

                print()
                print(
                    "Matched image:"
                )

                if src:
                    print(
                        src
                    )

                if srcset:
                    print(
                        srcset
                    )

                break

        return result

    except Exception as e:

        print(
            f"❌ ERROR: {e}"
        )

        return {
            "sku": sku,
            "found": False,
            "product_id": "",
            "name": "",
            "price": "",
            "available": "",
            "status": "EXCEPTION",
        }


def main():

    print("=" * 70)
    print("FILSTAR API SEARCH - PRICE + AVAILABILITY")
    print("=" * 70)

    # ---------------------------------------------------------
    # Зареждаме SKU
    # ---------------------------------------------------------

    skus = load_skus()

    print()
    print(
        f"Общо SKU: {len(skus)}"
    )

    # ---------------------------------------------------------
    # Проверяваме всички SKU
    # ---------------------------------------------------------

    results = []

    session = requests.Session()

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/131.0.0.0 "
            "Safari/537.36"
        ),
        "Accept": (
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "*/*;q=0.8"
        ),
        "Accept-Language": (
            "bg-BG,bg;q=0.9,en;q=0.8"
        ),
    })

    for index, sku in enumerate(
        skus,
        start=1
    ):

        print()
        print(
            f"[{index}/{len(skus)}]"
        )

        result = check_sku(
            session,
            sku
        )

        results.append(
            result
        )

        if WAIT > 0:
            time.sleep(WAIT)

    # ---------------------------------------------------------
    # Запис на резултатите
    # ---------------------------------------------------------

    output_file = (
        "results_filstar.csv"
    )

    fieldnames = [
        "sku",
        "found",
        "product_id",
        "name",
        "price",
        "available",
        "status",
    ]

    with open(
        output_file,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(
            results
        )

    # ---------------------------------------------------------
    # Обобщение
    # ---------------------------------------------------------

    available_count = sum(
        1
        for r in results
        if r["available"] == "YES"
    )

    unavailable_count = sum(
        1
        for r in results
        if r["available"] == "NO"
    )

    unknown_count = sum(
        1
        for r in results
        if r["available"] == "UNKNOWN"
    )

    not_found_count = sum(
        1
        for r in results
        if not r["found"]
    )

    print()
    print("=" * 70)
    print("ГОТОВО")
    print("=" * 70)

    print(
        f"Общо: {len(results)}"
    )

    print(
        f"Налични: {available_count}"
    )

    print(
        f"Неналични: {unavailable_count}"
    )

    print(
        f"UNKNOWN: {unknown_count}"
    )

    print(
        f"Ненамерени: {not_found_count}"
    )

    print()
    print(
        f"Резултатът е записан в: "
        f"{output_file}"
    )

    print()
    print("=" * 70)
    print("РЕЗУЛТАТИ")
    print("=" * 70)

    for result in results:

        print(
            f"{result['sku']} | "
            f"{result['price']} € | "
            f"{result['available']} | "
            f"{result['status']}"
        )


if __name__ == "__main__":
    main()

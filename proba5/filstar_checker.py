```text
import csv
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://filstar.com"
CSV_FILE = "sku_list_filstar.csv"

WAIT = 0


def load_skus():
    """
    Зарежда SKU от CSV.
    Всичко между два реда с точно ## се игнорира.
    """

    skus = []
    skip_block = False

    with open(CSV_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            sku = str(row.get("SKU", "")).strip()

            if sku == "##":
                skip_block = not skip_block
                continue

            if skip_block:
                continue

            if sku:
                skus.append(sku)

    return skus


def extract_product_data(html, sku):
    """
    Извлича цена и наличност от HTML-а на /api/search?term=SKU.
    """

    soup = BeautifulSoup(html, "html.parser")

    result = {
        "sku": sku,
        "found": False,
        "product_id": "",
        "name": "",
        "price": "",
        "available": "",
        "status": "",
    }

    # ---------------------------------------------------------
    # Проверяваме дали SKU изобщо присъства
    # ---------------------------------------------------------

    text = soup.get_text(" ", strip=True)

    if sku not in text:
        result["status"] = "SKU_NOT_FOUND"
        return result

    result["found"] = True

    # ---------------------------------------------------------
    # Намираме product блок, който съдържа конкретния SKU
    # ---------------------------------------------------------

    elements = soup.find_all(
        attrs={"data-product-id": True}
    )

    product_element = None

    for element in elements:

        current = element

        for _ in range(10):

            if current is None:
                break

            current_text = current.get_text(
                " ",
                strip=True
            )

            if sku in current_text:
                product_element = current
                break

            current = current.parent

        if product_element is not None:
            break

    # ---------------------------------------------------------
    # Ако не сме намерили data-product блок
    # ---------------------------------------------------------

    if product_element is None:

        result["status"] = (
            "SKU_FOUND_BUT_PRODUCT_BLOCK_NOT_FOUND"
        )

        return result

    # ---------------------------------------------------------
    # Product ID
    # ---------------------------------------------------------

    current = product_element

    for _ in range(10):

        if current is None:
            break

        product_id = current.get(
            "data-product-id"
        )

        if product_id:
            result["product_id"] = product_id
            break

        current = current.parent

    # ---------------------------------------------------------
    # Име
    # ---------------------------------------------------------

    name = (
        product_element.get(
            "data-product-name"
        )
        or product_element.get(
            "data-product-variant"
        )
        or ""
    )

    result["name"] = name.strip()

    # ---------------------------------------------------------
    # ЦЕНА
    # ---------------------------------------------------------

    block_text = product_element.get_text(
        " ",
        strip=True
    )

    price = ""

    price_patterns = [
        r"(\d+[.,]\d{2})\s*€",
        r"от\s*(\d+[.,]\d{2})\s*€",
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

    # Събираме класовете на елемента
    classes = product_element.get(
        "class",
        []
    )

    class_text = " ".join(
        classes
    ).lower()

    lower_text = block_text.lower()

    # Маркери за неналичност
    out_of_stock_markers = [
        "out-of-stock",
        "out of stock",
        "няма наличност",
        "неналичен",
        "изчерпан",
        "не е наличен",
    ]

    # Маркери за наличност
    available_markers = [
        "в наличност",
        "наличен",
    ]

    is_out_of_stock = any(
        marker in class_text
        or marker in lower_text
        for marker in out_of_stock_markers
    )

    is_available = any(
        marker in lower_text
        for marker in available_markers
    )

    if is_out_of_stock:

        result["available"] = "NO"
        result["status"] = "OUT_OF_STOCK"

    elif is_available:

        result["available"] = "YES"
        result["status"] = "AVAILABLE"

    else:

        result["available"] = "UNKNOWN"
        result["status"] = (
            "FOUND_NO_STOCK_MARKER"
        )

    return result


def check_sku(session, sku):

    url = f"{BASE_URL}/api/search"

    params = {
        "term": sku
    }

    print()
    print("=" * 70)
    print(f"SKU: {sku}")
    print("=" * 70)

    try:

        response = session.get(
            url,
            params=params,
            timeout=30
        )

        print(
            f"HTTP: {response.status_code}"
        )

        if response.status_code != 200:

            print(
                f"❌ HTTP ERROR: "
                f"{response.status_code}"
            )

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

        result = extract_product_data(
            html,
            sku
        )

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
            f"{result['price']}"
        )

        print(
            f"Available: "
            f"{result['available']}"
        )

        print(
            f"Status: "
            f"{result['status']}"
        )

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
    print("FILSTAR API SEARCH TEST")
    print("=" * 70)

    skus = load_skus()

    print(
        f"Общо SKU: {len(skus)}"
    )

    # Първите 10 SKU за тест
    test_skus = skus[:10]

    print(
        f"Тестови SKU: {len(test_skus)}"
    )

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
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": (
            "bg-BG,bg;q=0.9,en;q=0.8"
        ),
    })

    results = []

    for index, sku in enumerate(
        test_skus,
        start=1
    ):

        print()
        print(
            f"[{index}/{len(test_skus)}]"
        )

        result = check_sku(
            session,
            sku
        )

        results.append(result)

        if WAIT:
            time.sleep(WAIT)

    # ---------------------------------------------------------
    # Запис на резултатите
    # ---------------------------------------------------------

    output_file = "filstar_api_test.csv"

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

        writer.writerows(results)

    # ---------------------------------------------------------
    # Финален резултат
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("ГОТОВО")
    print("=" * 70)

    print(
        f"Резултат: {output_file}"
    )

    print()

    for result in results:

        print(
            f"{result['sku']} | "
            f"{result['price']} € | "
            f"{result['available']} | "
            f"{result['status']}"
        )


if __name__ == "__main__":
    main()
```

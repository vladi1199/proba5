import os
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://filstar.com"
DEBUG_DIR = "debug_html"

os.makedirs(DEBUG_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
}


def separator(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def main():

    sku = "946537"

    separator("FILSTAR PRODUCT LIST-VIEW TEST")

    url = f"{BASE_URL}/api/search?term={sku}"

    print(f"\nGET: {url}")

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )
    except Exception as e:
        print(f"REQUEST ERROR: {e}")
        return

    print(f"HTTP STATUS: {response.status_code}")
    print(
        f"CONTENT-TYPE: "
        f"{response.headers.get('Content-Type')}"
    )
    print(
        f"SIZE: {len(response.text):,} bytes"
    )

    if response.status_code != 200:
        print("\nREQUEST FAILED")
        print(response.text[:3000])
        return

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    containers = soup.select(
        ".product-item-wapper"
    )

    separator("PRODUCT CONTAINERS")

    print(
        f"TOTAL: {len(containers)}"
    )

    for i, container in enumerate(
        containers,
        start=1
    ):

        print(
            f"\nPRODUCT #{i}"
        )

        print(
            f"CLASS: {container.get('class')}"
        )

        print(
            f"SIZE: {len(str(container)):,}"
        )

        print(
            f"PRODUCT ID: "
            f"{container.get('data-product-id')}"
        )

        print(
            f"PRODUCT NAME: "
            f"{container.get('data-product-name')}"
        )

    # --------------------------------------------------
    # ТЪРСИМ PRODUCT-LIST-VIEW
    # --------------------------------------------------

    separator("TARGET: PRODUCT-LIST-VIEW")

    target = soup.select_one(
        ".product-item-wapper.product-list-view"
    )

    if not target:
        print(
            "PRODUCT-LIST-VIEW NOT FOUND"
        )
        return

    html = str(target)

    print(
        f"TARGET SIZE: {len(html):,} bytes"
    )

    # --------------------------------------------------
    # ВСИЧКИ АТРИБУТИ НА ВЪТРЕШНИТЕ ЕЛЕМЕНТИ
    # --------------------------------------------------

    separator("ALL INTERESTING ATTRIBUTES")

    for tag in target.find_all(True):

        interesting = False

        for key, value in tag.attrs.items():

            key_lower = str(key).lower()
            value_lower = str(value).lower()

            if (
                key_lower.startswith("data-")
                or "sku" in key_lower
                or "stock" in key_lower
                or "variant" in key_lower
                or "product" in key_lower
                or "price" in key_lower
                or "quantity" in key_lower
                or "barcode" in key_lower
                or "store" in key_lower
                or "sku" in value_lower
                or "946537" in value_lower
                or "8617" in value_lower
                or "8618" in value_lower
            ):
                interesting = True

        if interesting:

            print(
                f"\nTAG: <{tag.name}>"
            )

            for key, value in tag.attrs.items():

                print(
                    f"{key} = {value}"
                )

    # --------------------------------------------------
    # TEXT
    # --------------------------------------------------

    separator("VISIBLE TEXT")

    text = target.get_text(
        "\n",
        strip=True
    )

    print(text)

    # --------------------------------------------------
    # КЛЮЧОВИ ДУМИ
    # --------------------------------------------------

    separator("KEYWORD COUNTS INSIDE TARGET")

    terms = [
        "946537",
        "946534",
        "946535",

        "8617",
        "8618",

        "sku",
        "stock",
        "variant",
        "variants",
        "variantid",
        "productid",
        "barcode",

        "quantity",
        "price",
        "discountedprice",
        "originalprice",

        "store",
        "stores",

        "plovdiv",
        "sofia",
    ]

    lower_html = html.lower()

    for term in terms:

        count = lower_html.count(
            term.lower()
        )

        if count:

            print(
                f"{term}: {count}"
            )

    # --------------------------------------------------
    # КОНТЕКСТ ОКОЛО SKU / STOCK
    # --------------------------------------------------

    separator(
        "CONTEXT AROUND SKU / STOCK / VARIANT"
    )

    context_terms = [
        "946537",
        "sku",
        "stock",
        "variant",
        "variantid",
        "quantity",
        "price",
        "barcode",
        "store",
    ]

    already = set()

    for term in context_terms:

        start = 0

        while True:

            pos = lower_html.find(
                term.lower(),
                start
            )

            if pos == -1:
                break

            context_start = max(
                0,
                pos - 800
            )

            context_end = min(
                len(html),
                pos + len(term) + 1500
            )

            context = html[
                context_start:context_end
            ]

            key = (
                term,
                context_start
            )

            if key not in already:

                print()
                print(
                    f"--- {term} "
                    f"at {pos} ---"
                )

                print(context)

                already.add(key)

            start = pos + len(term)

            # Не допускаме безкраен лог
            if len(already) >= 25:
                break

        if len(already) >= 25:
            break

    # --------------------------------------------------
    # ВЪТРЕШЕН HTML
    # --------------------------------------------------

    separator("FULL TARGET HTML")

    print(html)

    # --------------------------------------------------
    # ЗАПИС
    # --------------------------------------------------

    path = os.path.join(
        DEBUG_DIR,
        "product_list_view_946537.html"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(html)

    print()
    print(
        f"DEBUG FILE SAVED: {path}"
    )

    separator("END OF TEST")


if __name__ == "__main__":
    main()

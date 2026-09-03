import re
from playwright.sync_api import sync_playwright

BASE_URL = "https://filstar.com"

SKU = "946537"

with sync_playwright() as p:

    print("Стартирам...")

    browser = p.chromium.launch(
        headless=True
    )

    page = browser.new_page()

    url = f"{BASE_URL}/api/search?term={SKU}"

    response = page.request.get(
        url,
        timeout=30000
    )

    print(
        "HTTP:",
        response.status
    )

    html = response.text()

    print(
        "HTML:",
        len(html),
        "characters"
    )

    # --------------------------------------------------------
    # Търсим SKU
    # --------------------------------------------------------

    pos = html.find(SKU)

    print(
        "SKU position:",
        pos
    )

    if pos >= 0:

        start = max(
            0,
            pos - 5000
        )

        end = min(
            len(html),
            pos + 10000
        )

        snippet = html[
            start:end
        ]

        print()
        print("=" * 70)
        print("КОНТЕКСТ ОКОЛО SKU")
        print("=" * 70)
        print()

        print(snippet)

    # --------------------------------------------------------
    # Търсим ключови думи за inventory
    # --------------------------------------------------------

    keywords = [
        "quantity",
        "available",
        "inventory",
        "stock",
        "variant",
        "barcode",
        "price",
        "product-id",
    ]

    print()
    print("=" * 70)
    print("ТЪРСЕНЕ НА ДАННИ")
    print("=" * 70)

    for keyword in keywords:

        count = len(
            re.findall(
                re.escape(keyword),
                html,
                re.IGNORECASE
            )
        )

        print(
            f"{keyword}: {count}"
        )

    # --------------------------------------------------------
    # Всички data-* атрибути
    # --------------------------------------------------------

    data_attributes = sorted(
        set(
            re.findall(
                r'\bdata-[a-zA-Z0-9_-]+',
                html
            )
        )
    )

    print()
    print("=" * 70)
    print("DATA ATTRIBUTES")
    print("=" * 70)

    for attr in data_attributes:

        print(
            attr
        )

    # --------------------------------------------------------
    # Записваме целия HTML
    # --------------------------------------------------------

    with open(
        "api_search_debug.html",
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            html
        )

    print()
    print(
        "💾 Запазен:"
    )

    print(
        "api_search_debug.html"
    )

    browser.close()

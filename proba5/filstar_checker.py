from playwright.sync_api import sync_playwright


BASE_URL = "https://filstar.com"
PRODUCT_ID = "2557"


with sync_playwright() as p:

    print("=" * 70)
    print("FILSTAR SERIALIZE TEST")
    print("=" * 70)

    browser = p.chromium.launch(
        headless=True
    )

    context = browser.new_context(
        viewport={
            "width": 1440,
            "height": 1000
        },
        locale="bg-BG"
    )

    page = context.new_page()

    # --------------------------------------------------------
    # 1. Отваряме началната страница
    # --------------------------------------------------------

    print()
    print("1. Отварям filstar.com...")

    try:

        response = page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        if response:
            print(
                f"   HTTP {response.status}"
            )

    except Exception as e:

        print(
            f"   ERROR: {e}"
        )

    # --------------------------------------------------------
    # 2. Директно проверяваме serialize endpoint-а
    # --------------------------------------------------------

    serialize_url = (
        f"{BASE_URL}"
        f"/get-serialize-product/"
        f"{PRODUCT_ID}"
    )

    print()
    print(
        "2. Проверявам:"
    )

    print(
        f"   {serialize_url}"
    )

    try:

        response = page.request.get(
            serialize_url,
            timeout=30000
        )

        print()
        print(
            f"   HTTP: {response.status}"
        )

        print(
            f"   Content-Type: "
            f"{response.headers.get('content-type')}"
        )

        text = response.text()

        print(
            f"   Length: "
            f"{len(text)}"
        )

        print()
        print("=" * 70)
        print("ПЪРВИТЕ 2000 СИМВОЛА")
        print("=" * 70)
        print()

        print(
            text[:2000]
        )

        # ----------------------------------------------------
        # Записваме отговора
        # ----------------------------------------------------

        with open(
            "serialize_debug.txt",
            "w",
            encoding="utf-8"
        ) as f:

            f.write(text)

        print()
        print(
            "💾 Запазен: serialize_debug.txt"
        )

    except Exception as e:

        print()
        print(
            f"❌ ERROR: {e}"
        )

    browser.close()

    print()
    print("=" * 70)
    print("КРАЙ")
    print("=" * 70)

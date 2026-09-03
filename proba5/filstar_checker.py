import requests
from bs4 import BeautifulSoup

BASE_URL = "https://filstar.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
}


def main():

    sku = "946537"

    url = f"{BASE_URL}/api/search?term={sku}"

    print("=" * 80)
    print("FILSTAR SEARCH PRODUCT LINK DIAGNOSTIC")
    print("=" * 80)

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    print(f"STATUS: {r.status_code}")
    print(f"SIZE: {len(r.text):,}")

    soup = BeautifulSoup(
        r.text,
        "html.parser"
    )

    # ---------------------------------------------------------
    # PRODUCT CONTAINER
    # ---------------------------------------------------------

    products = soup.select(
        ".product-item-wapper"
    )

    print()
    print("=" * 80)
    print("PRODUCT CONTAINERS")
    print("=" * 80)

    print(f"TOTAL: {len(products)}")

    for i, product in enumerate(products, 1):

        print()
        print(f"PRODUCT #{i}")
        print("-" * 60)

        print(
            "TEXT:",
            product.get_text(
                " ",
                strip=True
            )
        )

        # EVERY ATTRIBUTE
        for tag in product.find_all(True):

            attrs = tag.attrs

            if not attrs:
                continue

            print()
            print(f"<{tag.name}>")

            for key, value in attrs.items():

                print(
                    f"  {key} = {value}"
                )

    # ---------------------------------------------------------
    # ALL LINKS
    # ---------------------------------------------------------

    print()
    print("=" * 80)
    print("ALL LINKS IN SEARCH RESPONSE")
    print("=" * 80)

    links = soup.find_all("a")

    for i, a in enumerate(links, 1):

        href = a.get("href")

        if not href:
            continue

        text = a.get_text(
            " ",
            strip=True
        )

        print(
            f"{i}. HREF={href!r} | TEXT={text!r}"
        )

    # ---------------------------------------------------------
    # ALL FORMS
    # ---------------------------------------------------------

    print()
    print("=" * 80)
    print("FORMS")
    print("=" * 80)

    forms = soup.find_all("form")

    print(
        f"TOTAL FORMS: {len(forms)}"
    )

    for i, form in enumerate(forms, 1):

        print()
        print(f"FORM #{i}")

        for key, value in form.attrs.items():

            print(
                f"  {key} = {value}"
            )

        for field in form.find_all(
            ["input", "select", "button"]
        ):

            print(
                f"  FIELD <{field.name}> "
                f"{field.attrs}"
            )

    # ---------------------------------------------------------
    # ELEMENTS WITH STIMULUS / TURBO / ACTION
    # ---------------------------------------------------------

    print()
    print("=" * 80)
    print("STIMULUS / TURBO / ACTION ATTRIBUTES")
    print("=" * 80)

    for tag in soup.find_all(True):

        matches = {}

        for key, value in tag.attrs.items():

            key_lower = key.lower()

            if (
                key_lower.startswith("data-action")
                or key_lower.startswith("data-controller")
                or key_lower.startswith("data-target")
                or key_lower.startswith("data-")
                or key_lower.startswith("data-url")
                or key_lower.startswith("data-href")
                or key_lower.startswith("data-endpoint")
                or key_lower.startswith("data-path")
            ):
                matches[key] = value

        if matches:

            print()
            print(
                f"<{tag.name}>"
            )

            for key, value in matches.items():

                print(
                    f"  {key} = {value}"
                )

    print()
    print("=" * 80)
    print("END")
    print("=" * 80)


if __name__ == "__main__":
    main()

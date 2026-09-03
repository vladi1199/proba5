import requests
from bs4 import BeautifulSoup

BASE_URL = "https://filstar.com"
SKU = "946537"

url = f"{BASE_URL}/api/search"

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
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
})

print("=" * 70)
print("FILSTAR API SEARCH DEBUG")
print("=" * 70)

print(f"SKU: {SKU}")
print(f"URL: {url}?term={SKU}")

response = session.get(
    url,
    params={"term": SKU},
    timeout=30
)

print()
print(f"HTTP: {response.status_code}")
print(f"HTML: {len(response.text)} characters")

html = response.text

with open(
    "api_search_debug_current.html",
    "w",
    encoding="utf-8"
) as f:
    f.write(html)

print()
print("Записан файл:")
print("api_search_debug_current.html")

soup = BeautifulSoup(
    html,
    "html.parser"
)

print()
print("=" * 70)
print("DATA-PRODUCT ELEMENTS")
print("=" * 70)

elements = soup.find_all(
    attrs={"data-product-id": True}
)

print(
    f"Намерени елементи: {len(elements)}"
)

for index, element in enumerate(
    elements,
    start=1
):

    print()
    print("-" * 70)
    print(f"ELEMENT #{index}")
    print("-" * 70)

    print("TAG:", element.name)

    print()
    print("ATTRIBUTES:")

    for key, value in element.attrs.items():
        print(
            f"  {key} = {value}"
        )

    print()
    print("TEXT:")

    text = element.get_text(
        " ",
        strip=True
    )

    print(text[:2000])

print()
print("=" * 70)
print("SEARCHING RAW HTML")
print("=" * 70)

search_terms = [
    SKU,
    "946537",
    "data-product-id",
    "data-product-variant",
    "data-product-name",
    "discount-price",
    "out-of-stock",
    "product-list-view",
]

for term in search_terms:

    count = html.lower().count(
        term.lower()
    )

    print(
        f"{term}: {count}"
    )

print()
print("=" * 70)
print("SKU RAW HTML CONTEXT")
print("=" * 70)

position = html.find(SKU)

if position == -1:

    print(
        "SKU НЕ е намерен като обикновен текст "
        "в raw HTML."
    )

else:

    print(
        f"SKU намерен на позиция: {position}"
    )

    start = max(
        0,
        position - 3000
    )

    end = min(
        len(html),
        position + 5000
    )

    context = html[start:end]

    print(context)

    with open(
        "sku_context.txt",
        "w",
        encoding="utf-8"
    ) as f:
        f.write(context)

    print()
    print(
        "Контекстът е записан в sku_context.txt"
    )

print()
print("=" * 70)
print("ГОТОВО")
print("=" * 70)

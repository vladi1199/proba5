import requests
from bs4 import BeautifulSoup

BASE_URL = "https://filstar.com"
SKU = "946537"


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
print("FILSTAR SKU STRUCTURE DEBUG")
print("=" * 70)

url = f"{BASE_URL}/api/search"

print()
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

if response.status_code != 200:
    print()
    print("ERROR: HTTP", response.status_code)
    exit(1)

html = response.text

with open(
    "api_search_debug_current.html",
    "w",
    encoding="utf-8"
) as f:
    f.write(html)

print()
print("HTML записан в:")
print("api_search_debug_current.html")


print()
print("=" * 70)
print("ВСИЧКИ СРЕЩАНИЯ НА SKU")
print("=" * 70)

positions = []
start = 0

while True:

    position = html.find(
        SKU,
        start
    )

    if position == -1:
        break

    positions.append(position)

    start = position + len(SKU)


print()
print(
    f"Общо срещания: {len(positions)}"
)


for index, position in enumerate(
    positions,
    start=1
):

    print()
    print("-" * 70)
    print(
        f"СРЕЩАНЕ #{index} "
        f"на позиция {position}"
    )
    print("-" * 70)

    start_context = max(
        0,
        position - 800
    )

    end_context = min(
        len(html),
        position + 1200
    )

    context = html[
        start_context:end_context
    ]

    print(context)


print()
print("=" * 70)
print("SOUP ELEMENTS СЪДЪРЖАЩИ SKU")
print("=" * 70)

soup = BeautifulSoup(
    html,
    "html.parser"
)

elements = soup.find_all(
    lambda tag:
        tag.string is not None
        and SKU in tag.string
)

print()
print(
    f"Намерени директни text nodes: "
    f"{len(elements)}"
)


for index, element in enumerate(
    elements,
    start=1
):

    print()
    print("-" * 70)
    print(
        f"TEXT NODE #{index}"
    )
    print("-" * 70)

    print(
        "TAG:",
        element.name
    )

    print(
        "TEXT:",
        repr(element.string)
    )

    print(
        "ATTRIBUTES:"
    )

    for key, value in element.attrs.items():
        print(
            f"  {key} = {value}"
        )

    print()
    print(
        "PARENT:"
    )

    if element.parent:

        print(
            str(element.parent)[:5000]
        )


print()
print("=" * 70)
print("ЕЛЕМЕНТИ С DATA- АТРИБУТИ")
print("=" * 70)

data_elements = soup.find_all(
    attrs=lambda attrs:
        attrs and any(
            key.startswith("data-")
            for key in attrs
        )
)

sku_data_elements = []

for element in data_elements:

    element_html = str(
        element
    )

    if SKU in element_html:
        sku_data_elements.append(
            element
        )


print()
print(
    f"Data елементи, съдържащи SKU: "
    f"{len(sku_data_elements)}"
)


for index, element in enumerate(
    sku_data_elements,
    start=1
):

    print()
    print("-" * 70)
    print(
        f"DATA ELEMENT #{index}"
    )
    print("-" * 70)

    print(
        "TAG:",
        element.name
    )

    print(
        "ATTRIBUTES:"
    )

    for key, value in element.attrs.items():

        print(
            f"  {key} = {value}"
        )

    print()
    print(
        "HTML:"
    )

    print(
        str(element)[:5000]
    )


print()
print("=" * 70)
print("ГОТОВО")
print("=" * 70)

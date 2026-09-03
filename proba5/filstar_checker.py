#!/usr/bin/env python3

# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import requests
import shutil
import json
from urllib.parse import quote, urljoin

BASE_DIR = os.path.dirname(os.path.abspath(**file**))

SKU_CSV = os.path.join(
BASE_DIR,
"sku_list_filstar.csv"
)

RESULT_CSV = os.path.join(
BASE_DIR,
"results_filstar.csv"
)

NOT_FOUND_CSV = os.path.join(
BASE_DIR,
"not_found_filstar.csv"
)

DEBUG_DIR = os.path.join(
BASE_DIR,
"debug_html"
)

BASE_URL = "https://filstar.com"

WAIT = 2

HEADERS = {
"User-Agent":
"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
"AppleWebKit/537.36 (KHTML, like Gecko) "
"Chrome/128.0.0.0 Safari/537.36",

```
"Accept":
"text/html,application/xhtml+xml,application/xml;q=0.9,"
"application/json;q=0.8,*/*;q=0.7",

"Accept-Language":
"bg-BG,bg;q=0.9,en;q=0.8",

"Referer":
"https://filstar.com/"
```

}

session = requests.Session()
session.headers.update(HEADERS)

# =========================================================

# READ SKU

# =========================================================

def read_skus():

```
result = []
block = False

with open(
    SKU_CSV,
    encoding="utf-8-sig"
) as f:

    for line in f:

        line = line.strip()

        if not line:
            continue

        if line.upper() == "SKU":
            continue

        if line == "##":

            block = not block
            continue

        if block:
            continue

        result.append(line)

return result
```

# =========================================================

# INIT DEBUG FOLDER

# =========================================================

def init_debug_folder():

```
if os.path.exists(DEBUG_DIR):

    print(
        "🗑️ Изтривам старата debug папка:",
        DEBUG_DIR
    )

    try:

        shutil.rmtree(DEBUG_DIR)

    except Exception as e:

        print(
            "⚠️ Грешка при изтриване на debug папката:",
            e
        )

os.makedirs(
    DEBUG_DIR,
    exist_ok=True
)

print(
    "📁 Създадена е нова debug папка:",
    DEBUG_DIR
)
```

# =========================================================

# SAVE DEBUG

# =========================================================

def save_debug(filename, content):

```
if content is None:
    return

filepath = os.path.join(
    DEBUG_DIR,
    filename
)

try:

    with open(
        filepath,
        "w",
        encoding="utf-8"
    ) as f:

        if isinstance(content, str):

            f.write(content)

        else:

            json.dump(
                content,
                f,
                ensure_ascii=False,
                indent=2
            )

    print(
        "💾 Debug:",
        filepath
    )

except Exception as e:

    print(
        "⚠️ Грешка при запис на debug:",
        e
    )
```

# =========================================================

# INIT CSV

# =========================================================

def init_csv():

```
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
```

# =========================================================

# SAVE RESULT

# =========================================================

def save_result(row):

```
with open(
    RESULT_CSV,
    "a",
    newline="",
    encoding="utf-8"
) as f:

    csv.writer(f).writerow(row)
```

# =========================================================

# SAVE NOT FOUND

# =========================================================

def save_not_found(sku):

```
with open(
    NOT_FOUND_CSV,
    "a",
    newline="",
    encoding="utf-8"
) as f:

    csv.writer(f).writerow(
        [sku]
    )
```

# =========================================================

# SEARCH FILSTAR

# =========================================================

def search_filstar(sku):

```
url = (
    f"{BASE_URL}/api/search?term={quote(str(sku))}"
)

print(
    "🌐 SEARCH:",
    url
)

try:

    r = session.get(
        url,
        timeout=30
    )

    print(
        "🔎 Search HTTP:",
        r.status_code
    )

    html = r.text

    save_debug(
        f"search_{sku}.html",
        html
    )

    if r.status_code != 200:

        print(
            "❌ Search HTTP грешка:",
            r.status_code
        )

        return None

    return html

except Exception as e:

    print(
        "SEARCH ERROR:",
        e
    )

    return None
```

# =========================================================

# EXTRACT PRODUCT ID

# =========================================================

def extract_product_id(html):

```
if not html:
    return None

patterns = [

    r'data-product-id=["\'](\d+)["\']',

    r'/get-serialize-product/(\d+)',

    r'product.?id.?[:="\']+(\d+)',

]

ids = []

for pattern in patterns:

    matches = re.findall(
        pattern,
        html,
        re.I
    )

    ids.extend(matches)

ids = list(
    dict.fromkeys(ids)
)

print(
    "ID кандидати:",
    ids
)

if ids:
    return ids[0]

return None
```

# =========================================================

# EXTRACT PRODUCT URL

# =========================================================

def extract_product_url(html, sku):

```
if not html:
    return None

# -----------------------------------------------------
# Търсим href, който съдържа SKU
# -----------------------------------------------------

pattern = (
    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>'
    r'[\s\S]{0,1000}?'
    + re.escape(str(sku))
)

matches = re.findall(
    pattern,
    html,
    re.I
)

if matches:

    return urljoin(
        BASE_URL,
        matches[0]
    )

# -----------------------------------------------------
# Търсим product URL около SKU
# -----------------------------------------------------

sku_position = html.find(
    str(sku)
)

if sku_position != -1:

    start = max(
        0,
        sku_position - 5000
    )

    end = min(
        len(html),
        sku_position + 5000
    )

    nearby = html[
        start:end
    ]

    hrefs = re.findall(
        r'href=["\']([^"\']+)["\']',
        nearby,
        re.I
    )

    for href in hrefs:

        full_url = urljoin(
            BASE_URL,
            href
        )

        if (
            full_url.startswith(BASE_URL)
            and full_url.rstrip("/") != BASE_URL
        ):

            return full_url

return None
```

# =========================================================

# EXTRACT ALL PRODUCT URLS

# =========================================================

def extract_all_product_urls(html):

```
if not html:
    return []

urls = []

hrefs = re.findall(
    r'href=["\']([^"\']+)["\']',
    html,
    re.I
)

for href in hrefs:

    full_url = urljoin(
        BASE_URL,
        href
    )

    if full_url.startswith(BASE_URL):

        if full_url not in urls:

            urls.append(full_url)

return urls
```

# =========================================================

# TEST SEARCH-JSON-TYPESENSE

# =========================================================

def test_typesense_endpoint(sku):

```
print()
print(
    "================================================"
)
print(
    "🔬 TEST SEARCH-JSON-TYPESENSE"
)
print(
    "================================================"
)

endpoint = (
    f"{BASE_URL}/search-json-typesense"
)

tests = [

    (
        "q",
        {
            "q": str(sku)
        }
    ),

    (
        "term",
        {
            "term": str(sku)
        }
    ),

    (
        "query",
        {
            "query": str(sku)
        }
    ),

    (
        "q_query_by",
        {
            "q": str(sku),
            "query_by": "sku,name"
        }
    ),

    (
        "q_query_by_all",
        {
            "q": str(sku),
            "query_by": "*"
        }
    ),

]

results = []

for test_name, params in tests:

    print()
    print(
        "------------------------------------------------"
    )

    print(
        "🧪 TEST:",
        test_name
    )

    print(
        "📌 PARAMS:",
        params
    )

    try:

        request_headers = {

            "User-Agent":
            HEADERS["User-Agent"],

            "Accept":
            "application/json,text/plain,*/*",

            "Accept-Language":
            HEADERS["Accept-Language"],

            "Referer":
            f"{BASE_URL}/",

            "X-Requested-With":
            "XMLHttpRequest",

        }

        r = session.get(
            endpoint,
            params=params,
            headers=request_headers,
            timeout=30
        )

        print(
            "🔎 HTTP:",
            r.status_code
        )

        print(
            "📦 Content-Type:",
            r.headers.get(
                "Content-Type",
                ""
            )
        )

        print(
            "📏 Размер:",
            len(r.text),
            "bytes"
        )

        result_info = {

            "test": test_name,

            "params": params,

            "url": r.url,

            "status": r.status_code,

            "content_type":
            r.headers.get(
                "Content-Type",
                ""
            ),

            "length":
            len(r.text),

        }

        try:

            data = r.json()

            save_debug(
                f"typesense_{sku}_{test_name}.json",
                data
            )

            print(
                "✅ JSON:",
                type(data).__name__
            )

            serialized = json.dumps(
                data,
                ensure_ascii=False
            )

            if str(sku) in serialized:

                print(
                    "🎯 SKU Е НАМЕРЕНО В JSON!"
                )

                result_info[
                    "sku_found"
                ] = True

            else:

                print(
                    "❌ SKU не е намерено в JSON."
                )

                result_info[
                    "sku_found"
                ] = False

        except Exception as e:

            print(
                "⚠️ Response не е JSON:",
                e
            )

            save_debug(
                f"typesense_{sku}_{test_name}.txt",
                (
                    f"URL: {r.url}\n"
                    f"HTTP: {r.status_code}\n"
                    f"Content-Type: "
                    f"{r.headers.get('Content-Type', '')}\n"
                    f"Size: {len(r.text)}\n\n"
                    f"{r.text}"
                )
            )

        results.append(
            result_info
        )

    except Exception as e:

        print(
            "❌ TYPESENSE ERROR:",
            e
        )

        results.append(
            {
                "test": test_name,
                "params": params,
                "error": str(e)
            }
        )

save_debug(
    f"typesense_summary_{sku}.json",
    results
)

print()
print(
    "🔬 Typesense тестовете приключиха."
)
```

# =========================================================

# OPEN PRODUCT PAGE

# =========================================================

def get_product_page(
product_url,
sku
):

```
if not product_url:

    print(
        "⚠️ Няма Product URL."
    )

    return None

print()
print(
    "================================================"
)

print(
    "🌐 PRODUCT PAGE"
)

print(
    product_url
)

print(
    "================================================"
)

try:

    r = session.get(
        product_url,
        timeout=30
    )

    print(
        "🔎 Product HTTP:",
        r.status_code
    )

    print(
        "📏 Размер:",
        len(r.text),
        "bytes"
    )

    save_debug(
        f"product_{sku}.html",
        r.text
    )

    if r.status_code != 200:

        print(
            "❌ Product page HTTP грешка:",
            r.status_code
        )

        return None

    return r.text

except Exception as e:

    print(
        "PRODUCT PAGE ERROR:",
        e
    )

    return None
```

# =========================================================

# SCAN PRODUCT PAGE

# =========================================================

def scan_product_page(
html,
sku
):

```
if not html:
    return

print()
print(
    "================================================"
)

print(
    "🔬 SCAN PRODUCT PAGE"
)

print(
    "================================================"
)

keywords = [

    str(sku),

    "variants",

    "variant",

    "quantity",

    "discountedPrice",

    "discountedRetailPrice",

    "traderPrice",

    "stores",

    "maxQuantity",

    "data-product-id",

    "data-product-variant",

    "add-variant-to-cart",

    "getProductSerializeUrl",

    "get-serialize-product",

    "search-json-typesense",

]

all_matches = []

for keyword in keywords:

    context = extract_context(
        html,
        keyword,
        radius=2500
    )

    if context:

        print(
            "🎯 НАМЕРЕНО:",
            keyword
        )

        all_matches.append(
            context
        )

if all_matches:

    save_debug(
        f"product_{sku}_matches.txt",
        "\n".join(all_matches)
    )

# -----------------------------------------------------
# DATA-* атрибути
# -----------------------------------------------------

data_attributes = re.findall(
    r'data-[a-zA-Z0-9_-]+=["\'][^"\']*["\']',
    html,
    re.I
)

if data_attributes:

    unique_attributes = list(
        dict.fromkeys(
            data_attributes
        )
    )

    save_debug(
        f"product_{sku}_data_attributes.txt",
        "\n".join(unique_attributes)
    )

    print(
        "📦 Data attributes:",
        len(unique_attributes)
    )

# -----------------------------------------------------
# JSON SCRIPT BLOCKS
# -----------------------------------------------------

json_blocks = re.findall(
    r'<script[^>]*type=["\']application/json["\'][^>]*>'
    r'(.*?)'
    r'</script>',
    html,
    re.I | re.S
)

if json_blocks:

    print(
        "📦 JSON script блокове:",
        len(json_blocks)
    )

    for index, block in enumerate(
        json_blocks,
        1
    ):

        save_debug(
            f"product_{sku}_json_{index}.txt",
            block
        )

# -----------------------------------------------------
# INLINE JAVASCRIPT
# -----------------------------------------------------

scripts = re.findall(
    r'<script[^>]*>(.*?)</script>',
    html,
    re.I | re.S
)

print(
    "📜 Inline scripts:",
    len(scripts)
)

for index, script in enumerate(
    scripts,
    1
):

    interesting = False

    for keyword in keywords:

        if keyword.lower() in script.lower():

            interesting = True
            break

    if interesting:

        save_debug(
            f"product_{sku}_inline_script_{index}.js",
            script
        )
```

# =========================================================

# EXTRACT CONTEXT

# =========================================================

def extract_context(
text,
keyword,
radius=1200
):

```
if not text:
    return ""

lower_text = text.lower()
lower_keyword = keyword.lower()

positions = []

start = 0

while True:

    pos = lower_text.find(
        lower_keyword,
        start
    )

    if pos == -1:
        break

    positions.append(
        pos
    )

    start = pos + len(
        lower_keyword
    )

if not positions:
    return ""

chunks = []

for index, pos in enumerate(
    positions[:30],
    1
):

    chunk_start = max(
        0,
        pos - radius
    )

    chunk_end = min(
        len(text),
        pos + len(keyword) + radius
    )

    chunk = text[
        chunk_start:chunk_end
    ]

    chunks.append(
        "\n\n"
        + "=" * 80
        + f"\nMATCH #{index}: {keyword}\n"
        + "=" * 80
        + "\n"
        + chunk
    )

return "".join(
    chunks
)
```

# =========================================================

# SCAN SEARCH HTML FOR SKU

# =========================================================

def scan_search_for_sku(
html,
sku
):

```
if not html:
    return

print()
print(
    "🔎 Търся SKU в search HTML:",
    sku
)

context = extract_context(
    html,
    str(sku),
    radius=3000
)

if context:

    print(
        "🎯 SKU намерено в search HTML!"
    )

    save_debug(
        f"search_{sku}_sku_context.txt",
        context
    )

else:

    print(
        "❌ SKU не е намерено в search HTML."
    )
```

# =========================================================

# EXTRACT JAVASCRIPT URLS

# =========================================================

def extract_javascript_urls(
html
):

```
if not html:
    return []

urls = []

patterns = [

    r'<script[^>]+src=["\']([^"\']+)["\']',

    r'<script[^>]+src=([^ >]+)',

]

for pattern in patterns:

    matches = re.findall(
        pattern,
        html,
        re.I
    )

    for src in matches:

        src = src.strip()

        src = src.strip(
            "\"'"
        )

        if not src:
            continue

        if src.startswith("//"):

            src = "https:" + src

        elif src.startswith("/"):

            src = BASE_URL + src

        elif src.startswith("http://"):

            src = "https://" + src[7:]

        elif not src.startswith("http"):

            src = BASE_URL + "/" + src.lstrip("/")

        if src not in urls:

            urls.append(
                src
            )

return urls
```

# =========================================================

# SCAN JAVASCRIPT

# =========================================================

def scan_javascript(
html
):

```
print()
print(
    "================================================"
)

print(
    "🔬 JAVASCRIPT SCANNER"
)

print(
    "================================================"
)

js_urls = extract_javascript_urls(
    html
)

print(
    "📜 Намерени JS файлове:",
    len(js_urls)
)

save_debug(
    "javascript_urls.txt",
    "\n".join(js_urls)
)

keywords = [

    "search-json-typesense",

    "Typesense",

    "typesense",

    "query_by",

    "queryBy",

    "search-url",

    "searchUrl",

    "autocomplete",

    "get-serialize-product",

    "getProductSerializeUrl",

    "addToCartUrl",

    "discountedPrice",

    "quantity",

    "variants",

]

all_matches = []

for index, url in enumerate(
    js_urls,
    1
):

    print()
    print(
        "------------------------------------------------"
    )

    print(
        f"📥 JS {index}/{len(js_urls)}"
    )

    print(
        url
    )

    try:

        r = session.get(
            url,
            timeout=30
        )

        print(
            "   HTTP:",
            r.status_code
        )

        if r.status_code != 200:

            print(
                "   ❌ JS недостъпен"
            )

            continue

        js = r.text

        save_debug(
            f"js_{index}.js",
            js
        )

        file_matches = []

        for keyword in keywords:

            if keyword.lower() not in js.lower():
                continue

            print(
                "   🎯 НАМЕРЕНО:",
                keyword
            )

            context = extract_context(
                js,
                keyword,
                radius=2500
            )

            if context:

                file_matches.append(
                    context
                )

        if file_matches:

            save_debug(
                f"js_{index}_matches.txt",
                "\n".join(file_matches)
            )

            all_matches.extend(
                file_matches
            )

    except Exception as e:

        print(
            "   ❌ JS ERROR:",
            e
        )

if all_matches:

    save_debug(
        "ALL_JAVASCRIPT_MATCHES.txt",
        "\n".join(all_matches)
    )

print()
print(
    "🔬 JAVASCRIPT SCANNER ГОТОВ"
)
```

# =========================================================

# MAIN

# =========================================================

def main():

```
init_debug_folder()

init_csv()

skus = read_skus()

print(
    "Общо SKU:",
    len(skus)
)

scanner_done = False

# -----------------------------------------------------
# Диагностично тестваме само първите 3 SKU.
# -----------------------------------------------------

test_skus = skus[:3]

print(
    "🧪 Диагностичен режим."
)

print(
    "🧪 Ще бъдат тествани SKU:",
    test_skus
)

for sku in test_skus:

    print()
    print(
        "================================================"
    )

    print(
        "➡️ SKU:",
        sku
    )

    print(
        "================================================"
    )

    # -------------------------------------------------
    # SEARCH API
    # -------------------------------------------------

    html = search_filstar(
        sku
    )

    if not html:

        print(
            "❌ Няма search резултат."
        )

        save_not_found(
            sku
        )

        continue

    # -------------------------------------------------
    # SEARCH HTML
    # -------------------------------------------------

    scan_search_for_sku(
        html,
        sku
    )

    # -------------------------------------------------
    # JAVASCRIPT SCANNER
    # -------------------------------------------------

    if not scanner_done:

        scan_javascript(
            html
        )

        scanner_done = True

    # -------------------------------------------------
    # PRODUCT ID
    # -------------------------------------------------

    product_id = extract_product_id(
        html
    )

    if product_id:

        print(
            "✅ Product ID:",
            product_id
        )

    else:

        print(
            "⚠️ Product ID не е намерено."
        )

    # -------------------------------------------------
    # PRODUCT URL
    # -------------------------------------------------

    product_url = extract_product_url(
        html,
        sku
    )

    if product_url:

        print(
            "🔗 Product URL:",
            product_url
        )

    else:

        print(
            "⚠️ Product URL не е намерено."
        )

    # -------------------------------------------------
    # ВСИЧКИ URL
    # -------------------------------------------------

    product_urls = extract_all_product_urls(
        html
    )

    save_debug(
        f"search_{sku}_all_urls.txt",
        "\n".join(product_urls)
    )

    # -------------------------------------------------
    # TYPESENSE
    # -------------------------------------------------

    test_typesense_endpoint(
        sku
    )

    # -------------------------------------------------
    # PRODUCT PAGE
    # -------------------------------------------------

    product_html = get_product_page(
        product_url,
        sku
    )

    if product_html:

        scan_product_page(
            product_html,
            sku
        )

    # -------------------------------------------------
    # Засега не записваме реален резултат.
    # -------------------------------------------------

    save_not_found(
        sku
    )

    time.sleep(
        WAIT
    )

print()
print(
    "================================================"
)

print(
    "✅ ДИАГНОСТИКАТА ПРИКЛЮЧИ"
)

print(
    "================================================"
)

print(
    "💾 Debug:",
    DEBUG_DIR
)

print(
    "💾 Results:",
    RESULT_CSV
)

print(
    "💾 Not found:",
    NOT_FOUND_CSV
)

print()
print(
    "👉 Тествахме само първите 3 SKU."
)

print(
    "👉 /get-serialize-product/ НЕ Е ИЗПОЛЗВАН."
)

print(
    "👉 /search-json-typesense е тестван с няколко параметъра."
)

print(
    "👉 Продуктовите страници са сканирани."
)

print(
    "👉 Готово."
)
```

if **name** == "**main**":

```
main()
```

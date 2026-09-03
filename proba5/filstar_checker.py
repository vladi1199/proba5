import os
import re
import json
import requests

BASE_URL = "https://filstar.com"
DEBUG_DIR = "debug_html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

JS_FILES = [
    "/build/runtime.d94b3b43.js",
    "/build/0.eab9a25b.js",
    "/build/2.894e9701.js",
    "/build/app.6298546b.js",
]

SEARCH_TERMS = [
    "search-json-typesense",
    "/api/search",
    "get-serialize-product",
    "serialize",
    "variants",
    "defaultVariant",
    "quantity",
    "discountedPrice",
    "productId",
    "variantId",
    "sku",
    "barcode",
    "stores",
    "add-variant-to-cart",
    "search-autocomplete",
]


def save_text(filename, content):
    os.makedirs(DEBUG_DIR, exist_ok=True)

    path = os.path.join(DEBUG_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


def search_terms_in_text(text):
    found = {}

    lower = text.lower()

    for term in SEARCH_TERMS:
        positions = []

        start = 0

        while True:
            pos = lower.find(term.lower(), start)

            if pos == -1:
                break

            positions.append(pos)
            start = pos + len(term)

        if positions:
            found[term] = positions

    return found


def extract_context(text, position, radius=1500):
    start = max(0, position - radius)
    end = min(len(text), position + radius)

    return text[start:end]


def inspect_source_map(session, js_url):
    map_url = js_url + ".map"

    print()
    print("-" * 70)
    print("SOURCE MAP")
    print("-" * 70)

    print(f"URL: {map_url}")

    try:
        response = session.get(
            map_url,
            headers=HEADERS,
            timeout=30
        )

        print(
            f"HTTP: {response.status_code}"
        )

        print(
            f"Content-Type: "
            f"{response.headers.get('Content-Type', '')}"
        )

        print(
            f"Size: {len(response.content):,} bytes"
        )

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return

    if response.status_code != 200:
        print("❌ Source map is not accessible.")
        return

    content = response.text

    save_text(
        os.path.basename(map_url),
        content
    )

    print("✅ Source map accessible!")

    # --------------------------------------------------------
    # Try JSON
    # --------------------------------------------------------

    try:
        data = response.json()

        print()
        print("JSON source map detected.")

        print(
            f"Version: {data.get('version')}"
        )

        print(
            f"Sources: "
            f"{len(data.get('sources', []))}"
        )

        print(
            f"SourcesContent: "
            f"{len(data.get('sourcesContent', []))}"
        )

        print()

        sources = data.get("sources", [])
        sources_content = data.get("sourcesContent", [])

        for i, source_name in enumerate(sources):

            source_content = ""

            if i < len(sources_content):
                source_content = (
                    sources_content[i] or ""
                )

            combined = (
                source_name
                + "\n"
                + source_content
            )

            found = search_terms_in_text(
                combined
            )

            if not found:
                continue

            print()
            print(
                "=" * 70
            )

            print(
                f"SOURCE #{i + 1}: {source_name}"
            )

            print(
                "=" * 70
            )

            for term, positions in found.items():

                print(
                    f"   🔎 {term}: "
                    f"{len(positions)} occurrence(s)"
                )

                # максимум 10 контекста
                for occurrence, pos in enumerate(
                    positions[:10],
                    start=1
                ):

                    context = extract_context(
                        combined,
                        pos,
                        radius=1200
                    )

                    print()
                    print(
                        f"   --- {term} #{occurrence} ---"
                    )

                    print(context)

                    save_text(
                        (
                            f"map_source_{i + 1}_"
                            f"{term.replace('/', '_')}_"
                            f"{occurrence}.txt"
                        ),
                        context
                    )

        # ----------------------------------------------------
        # Also inspect entire source map
        # ----------------------------------------------------

        found = search_terms_in_text(
            content
        )

        print()
        print(
            "=" * 70
        )

        print("WHOLE SOURCE MAP SEARCH")
        print(
            "=" * 70
        )

        for term, positions in found.items():

            print(
                f"   {term}: "
                f"{len(positions)} occurrence(s)"
            )

    except Exception as e:

        print(
            f"⚠️ Не е валиден стандартен JSON source map: {e}"
        )

        # ----------------------------------------------------
        # Raw text search
        # ----------------------------------------------------

        found = search_terms_in_text(
            content
        )

        for term, positions in found.items():

            print()
            print(
                f"🔎 {term}: "
                f"{len(positions)} occurrence(s)"
            )

            for occurrence, pos in enumerate(
                positions[:10],
                start=1
            ):

                context = extract_context(
                    content,
                    pos,
                    radius=1500
                )

                print()
                print(
                    f"--- {term} #{occurrence} ---"
                )

                print(context)


def inspect_js(session, js_url):
    print()
    print("=" * 70)
    print("JAVASCRIPT")
    print("=" * 70)

    print(f"URL: {js_url}")

    try:
        response = session.get(
            BASE_URL + js_url,
            headers=HEADERS,
            timeout=30
        )

        print(
            f"HTTP: {response.status_code}"
        )

        print(
            f"Content-Type: "
            f"{response.headers.get('Content-Type', '')}"
        )

        print(
            f"Size: {len(response.content):,} bytes"
        )

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return

    # Записваме JS независимо дали е 200 или 403
    filename = (
        "js_"
        + os.path.basename(js_url)
        + ".txt"
    )

    save_text(
        filename,
        response.text
    )

    if response.status_code == 200:

        found = search_terms_in_text(
            response.text
        )

        if found:

            print()
            print(
                "Намерени термини:"
            )

            for term, positions in found.items():

                print(
                    f"   🔎 {term}: "
                    f"{len(positions)}"
                )

                for occurrence, pos in enumerate(
                    positions[:5],
                    start=1
                ):

                    context = extract_context(
                        response.text,
                        pos,
                        radius=1000
                    )

                    save_text(
                        (
                            f"js_"
                            f"{os.path.basename(js_url)}_"
                            f"{term.replace('/', '_')}_"
                            f"{occurrence}.txt"
                        ),
                        context
                    )

                    print(
                        f"      Context #{occurrence} saved"
                    )

        else:
            print(
                "⚠️ JS е достъпен, но търсените "
                "термини не са намерени."
            )

    else:
        print(
            "❌ JS не е достъпен."
        )

    # --------------------------------------------------------
    # Source map
    # --------------------------------------------------------

    inspect_source_map(
        session,
        BASE_URL + js_url
    )


def main():

    print("=" * 70)
    print("FILSTAR JAVASCRIPT / SOURCE MAP DIAGNOSTIC")
    print("=" * 70)

    os.makedirs(
        DEBUG_DIR,
        exist_ok=True
    )

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    # --------------------------------------------------------
    # Test every JS
    # --------------------------------------------------------

    for index, js_file in enumerate(
        JS_FILES,
        start=1
    ):

        print()
        print(
            f"### JS {index}/{len(JS_FILES)} ###"
        )

        inspect_js(
            session,
            js_file
        )

    # --------------------------------------------------------
    # Try source maps directly one more time
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("DIRECT SOURCE MAP SUMMARY")
    print("=" * 70)

    accessible = []

    for js_file in JS_FILES:

        map_url = BASE_URL + js_file + ".map"

        try:
            response = session.get(
                map_url,
                headers=HEADERS,
                timeout=30
            )

            status = response.status_code

            print(
                f"{os.path.basename(map_url)} "
                f"→ HTTP {status}, "
                f"{len(response.content):,} bytes"
            )

            if status == 200:
                accessible.append(
                    map_url
                )

        except Exception as e:

            print(
                f"{os.path.basename(map_url)} "
                f"→ ERROR {e}"
            )

    print()

    if accessible:

        print(
            "✅ ДОСТЪПНИ SOURCE MAP ФАЙЛОВЕ:"
        )

        for url in accessible:
            print(
                f"   {url}"
            )

    else:

        print(
            "❌ Няма достъпен source map."
        )

    print()
    print("=" * 70)
    print("DIAGNOSTIC FINISHED")
    print("=" * 70)

    print()
    print(
        f"Debug folder: {DEBUG_DIR}"
    )

    print()
    print(
        "Търсени термини:"
    )

    for term in SEARCH_TERMS:
        print(
            f"   - {term}"
        )


if __name__ == "__main__":
    main()

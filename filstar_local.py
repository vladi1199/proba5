#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filstar stock/price scraper - LOCAL runner.

Why local: filstar.com sits behind Cloudflare, which serves a managed
challenge ("Един момент...") to datacenter IPs. GitHub Actions is blocked
outright - verified with plain requests AND a real headed Chromium, both 403.
A normal home connection (or a VPN exit that isn't flagged) gets 200 with no
browser needed. So this runs on a desktop, not in CI.

What it does differently from the old scraper:
  * reads the PRODUCT page, not just /api/search, so it sees each variant
    separately. /api/search resolves every variant SKU to its parent card,
    which is why sibling SKUs used to share one stock value.
  * emits REAL quantities. The old feed wrote <quantity/> on every row.
  * one product page resolves ALL of that product's variants, so sibling
    SKUs cost no extra requests.
  * caches to disk, so an interrupted run resumes instead of restarting.

Output matches what nasluka-feeds already reads:
    <products><item><sku/><price/><quantity/><availability/></item>...</products>
"""

import argparse
import base64
import configparser
import csv
import html as H
import json
import os
import re
import sys
import time

import requests

BASE = "https://filstar.com"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

VARIANT_RE = re.compile(r':variant="((?:&quot;|[^"])*?)"')
PRODUCT_LINK_RE = re.compile(r'<div class="product-image">\s*<a href="([^"]+)"')

CACHE_DIR = ".cache"
URL_CACHE = os.path.join(CACHE_DIR, "sku_to_url.json")
VAR_CACHE = os.path.join(CACHE_DIR, "url_to_variants.json")


class Blocked(Exception):
    """Cloudflare challenged us - the exit IP is flagged."""


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    os.replace(tmp, path)


def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    })
    return s


def check(resp):
    if resp.status_code in (403, 429, 503):
        raise Blocked(
            "HTTP %s from %s\n"
            "Cloudflare is challenging this connection. Connect the VPN (or "
            "switch to a different exit) and run again - the cache means you "
            "resume where you stopped." % (resp.status_code, resp.url)
        )
    resp.raise_for_status()
    return resp


def read_skus(path):
    skus, seen = [], set()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.reader(fh):
            if not row:
                continue
            v = (row[0] or "").strip().strip('"')
            if not v or not v[0].isdigit():
                continue
            if v not in seen:
                seen.add(v)
                skus.append(v)
    return skus


def product_url(session, sku, delay):
    r = check(session.get(BASE + "/api/search", params={"term": sku}, timeout=30))
    time.sleep(delay)
    m = PRODUCT_LINK_RE.search(r.text)
    return BASE + m.group(1) if m else None


def variants_of(session, url, delay):
    r = check(session.get(url, timeout=60))
    time.sleep(delay)
    out = {}
    for raw in VARIANT_RE.findall(r.text):
        try:
            v = json.loads(H.unescape(raw))
        except Exception:
            continue
        sku = str(v.get("sku") or "").strip()
        if not sku:
            continue
        out[sku] = {
            "quantity": int(v.get("quantity") or 0),
            "price": round(float(v.get("price") or 0), 2),
            "trader_price": v.get("traderPrice"),
            "model": v.get("model") or "",
            "barcode": v.get("barcode") or "",
        }
    return out


def app_dir():
    """Directory the app lives in - works frozen (PyInstaller) or as a script."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def read_settings():
    """settings.ini next to the app. Absent or incomplete means 'do not upload'."""
    path = os.path.join(app_dir(), "settings.ini")
    if not os.path.exists(path):
        return None
    cp = configparser.ConfigParser()
    try:
        cp.read(path, encoding="utf-8")
        repo = cp.get("github", "repo", fallback="").strip()
        token = cp.get("github", "token", fallback="").strip()
        branch = cp.get("github", "branch", fallback="main").strip() or "main"
        if not repo or not token:
            return None
        return {"repo": repo, "token": token, "branch": branch}
    except Exception:
        return None


def upload_file(cfg, local_path, remote_path):
    """Create or update one file through the GitHub contents API."""
    api = "https://api.github.com/repos/%s/contents/%s" % (cfg["repo"], remote_path)
    headers = {
        "Authorization": "Bearer %s" % cfg["token"],
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with open(local_path, "rb") as fh:
        content = base64.b64encode(fh.read()).decode("ascii")

    sha = None
    r = requests.get(api, headers=headers,
                     params={"ref": cfg["branch"]}, timeout=60)
    if r.status_code == 200:
        sha = r.json().get("sha")
    elif r.status_code == 401:
        raise RuntimeError("Токенът в settings.ini е невалиден или изтекъл.")
    elif r.status_code == 404 and "/" not in cfg["repo"]:
        raise RuntimeError("repo в settings.ini трябва да е във вида "
                           "'потребител/хранилище'.")

    payload = {
        "message": "Stock update %s" % time.strftime("%Y-%m-%d %H:%M"),
        "content": content,
        "branch": cfg["branch"],
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(api, headers=headers, json=payload, timeout=120)
    if r.status_code not in (200, 201):
        detail = ""
        try:
            detail = r.json().get("message", "")
        except Exception:
            pass
        raise RuntimeError("GitHub отказа %s (HTTP %s) %s"
                           % (remote_path, r.status_code, detail))


def publish(cfg, paths):
    print("")
    print("  Качване в GitHub (%s, клон %s)..." % (cfg["repo"], cfg["branch"]))
    for p in paths:
        if not os.path.exists(p):
            continue
        name = os.path.basename(p)
        upload_file(cfg, p, name)
        print("    качено: %s" % name)
    print("  Готово.")


def write_outputs(rows, per_file, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    csv_path = os.path.join(out_dir, "results_filstar.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["SKU", "Наличност", "Бройки", "Цена", "Цена на едро", "Модел"])
        for sku, v in rows.items():
            w.writerow([
                sku,
                "Наличен" if v["quantity"] > 0 else "Неналичен",
                v["quantity"],
                "%.2f" % v["price"],
                v["trader_price"] if v["trader_price"] is not None else "",
                v["model"],
            ])

    items = list(rows.items())
    files = []
    for i in range(0, len(items), per_file):
        chunk = items[i:i + per_file]
        n = i // per_file + 1
        path = os.path.join(out_dir, "filstar_xml_%d.xml" % n)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<products>')
            for sku, v in chunk:
                avail = "in_stock" if v["quantity"] > 0 else "out_of_stock"
                fh.write(
                    "<item><sku>%s</sku><price>%.2f</price>"
                    "<quantity>%d</quantity><availability>%s</availability></item>"
                    % (sku, v["price"], v["quantity"], avail)
                )
            fh.write("</products>\n")
        files.append((path, len(chunk)))
    return csv_path, files


def main():
    ap = argparse.ArgumentParser(description="Filstar scraper (run locally)")
    ap.add_argument("--skus", default="sku_list_filstar.csv",
                    help="CSV whose first column is the SKU")
    ap.add_argument("--out", default=".", help="where to write CSV and XML")
    ap.add_argument("--delay", type=float, default=0.7,
                    help="seconds between requests (default 0.7)")
    ap.add_argument("--per-file", type=int, default=1400,
                    help="items per XML file (default 1400)")
    ap.add_argument("--limit", type=int, default=0,
                    help="only process the first N SKUs - use for a test run")
    ap.add_argument("--fresh", action="store_true",
                    help="ignore the cache and refetch everything")
    ap.add_argument("--no-upload", action="store_true",
                    help="never upload, even if settings.ini exists")
    args = ap.parse_args()

    if args.fresh:
        for p in (URL_CACHE, VAR_CACHE):
            if os.path.exists(p):
                os.remove(p)

    skus = read_skus(args.skus)
    if args.limit:
        skus = skus[:args.limit]
    print("")
    print("  Filstar stock update")
    print("  %d SKUs to check. This takes a while - you can leave it running." % len(skus))
    print("  Safe to stop with Ctrl+C; running it again resumes where it stopped.")
    print("")

    sku_to_url = load_json(URL_CACHE, {})
    url_to_variants = load_json(VAR_CACHE, {})

    session = make_session()
    resolved, not_found = {}, []
    pending = list(skus)
    wanted = set(skus)
    searches = fetches = 0
    t0 = time.time()
    last_report = 0.0

    try:
        while pending:
            sku = pending.pop(0)
            if sku in resolved:
                continue

            url = sku_to_url.get(sku)
            if url is None:
                url = product_url(session, sku, args.delay)
                searches += 1
                sku_to_url[sku] = url or ""
                if searches % 25 == 0:
                    save_json(URL_CACHE, sku_to_url)
            if not url:
                not_found.append(sku)
                continue

            variants = url_to_variants.get(url)
            if variants is None:
                variants = variants_of(session, url, args.delay)
                fetches += 1
                url_to_variants[url] = variants
                save_json(VAR_CACHE, url_to_variants)

            for s, v in variants.items():
                if s in wanted:
                    resolved[s] = v
                sku_to_url.setdefault(s, url)

            if sku not in resolved:
                not_found.append(sku)

            done = len(resolved) + len(not_found)
            now = time.time()
            if now - last_report >= 15 or not pending:
                last_report = now
                rate = done / max(now - t0, 1)
                left = (len(skus) - done) / max(rate, 0.01)
                pct = 100.0 * done / max(len(skus), 1)
                print("  %5.1f%%  %d/%d done   in stock so far %d   "
                      "requests %d   about %d min left"
                      % (pct, done, len(skus), sum(1 for v in resolved.values()
                                                   if v["quantity"] > 0),
                         searches + fetches, left / 60))
                sys.stdout.flush()

    except Blocked as e:
        save_json(URL_CACHE, sku_to_url)
        save_json(VAR_CACHE, url_to_variants)
        sys.stderr.write("\nSTOPPED: %s\n" % e)
        sys.exit(2)
    except KeyboardInterrupt:
        save_json(URL_CACHE, sku_to_url)
        save_json(VAR_CACHE, url_to_variants)
        sys.stderr.write("\nInterrupted - progress saved, rerun to resume.\n")
        sys.exit(130)

    save_json(URL_CACHE, sku_to_url)
    save_json(VAR_CACHE, url_to_variants)

    if not_found:
        with open(os.path.join(args.out, "not_found_filstar.csv"), "w",
                  encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["SKU"])
            for s in not_found:
                w.writerow([s])

    csv_path, files = write_outputs(resolved, args.per_file, args.out)
    in_stock = sum(1 for v in resolved.values() if v["quantity"] > 0)

    print("\nDone in %.1f min" % ((time.time() - t0) / 60))
    print("  resolved     %d  (in stock %d, out %d)"
          % (len(resolved), in_stock, len(resolved) - in_stock))
    print("  not found    %d" % len(not_found))
    print("  requests     %d searches + %d product pages = %d (vs %d with the old approach)"
          % (searches, fetches, searches + fetches, len(skus)))
    print("  wrote        %s" % csv_path)
    for p, n in files:
        print("               %s  (%d items)" % (p, n))

    if args.no_upload:
        return
    cfg = read_settings()
    if cfg is None:
        print("")
        print("  (няма settings.ini - файловете остават само тук)")
        return
    try:
        paths = [csv_path] + [p for p, _ in files]
        nf = os.path.join(args.out, "not_found_filstar.csv")
        if os.path.exists(nf):
            paths.append(nf)
        publish(cfg, paths)
    except Exception as e:
        sys.stderr.write("\n  Качването не успя: %s\n" % e)
        sys.stderr.write("  Файловете са запазени тук и може да се качат по-късно.\n")
        sys.exit(3)


if __name__ == "__main__":
    main()

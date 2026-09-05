# Filstar scraper — local runner

## Why this runs on a desktop and not on GitHub

filstar.com is behind Cloudflare. Product pages return **403 "Един момент..."**
to datacenter IPs. Verified from a GitHub Actions runner with:

* plain `requests` — 403
* full browser headers — 403
* homepage first for cookies — 403 (the homepage 403s too)
* search first, then product with a Referer — 403
* **a real headed Chromium under xvfb, automation flags stripped — 403**

It is IP reputation, not the browser and not the headers, so no user-agent
trick or login cookie fixes it (`cf_clearance` is bound to the IP that earned
it). A normal home connection, or a VPN exit that isn't flagged, gets 200 with
no browser at all.

`https://filstar.com/api/search` is the one exception — it answers 200 even
from GitHub. That is why the old scraper still half-works. But search resolves
**every variant SKU to its parent product**, so sibling SKUs all share one
stock value. Per-variant stock only exists on the product page.

## What you get that the old feed didn't

* **real quantities** — the old feed wrote `<quantity/>` on every row
* **per-variant stock** — 946534/35/36/37 come back as 876 / 593 / 785 / 82
  where search reported them as one identical blob
* wholesale price (`traderPrice`) alongside retail, in the CSV
* far fewer requests: one product page resolves all of that product's
  variants, so siblings cost nothing

## Running it

Needs Python 3.8+ and one dependency.

```bash
pip install requests
```

**Connect the VPN first.** Then:

```bash
# test run - 40 SKUs, about a minute
python3 filstar_local.py --skus sku_list_filstar.csv --limit 40

# the real thing
python3 filstar_local.py --skus sku_list_filstar.csv
```

Expect roughly 1–2 hours for a full list. Progress prints as it goes.

### If it stops

```
STOPPED: HTTP 403 ... Cloudflare is challenging this connection.
```

The VPN dropped or that exit is flagged. Switch exit, run the same command
again — it caches to `.cache/` and resumes where it stopped rather than
starting over. Ctrl+C is safe for the same reason.

### Options

| flag | meaning |
|---|---|
| `--skus FILE` | CSV whose first column is the SKU (default `sku_list_filstar.csv`) |
| `--out DIR` | where to write CSV and XML (default: current directory) |
| `--delay N` | seconds between requests, default 1.0. Lower is faster and ruder |
| `--limit N` | only the first N SKUs — for testing |
| `--per-file N` | items per XML file, default 1400 |
| `--fresh` | ignore the cache and refetch everything |

## Output

* `results_filstar.csv` — SKU, наличност, бройки, цена, цена на едро, модел
* `filstar_xml_1.xml`, `_2.xml`, … — 1400 items each
* `not_found_filstar.csv` — SKUs the search could not resolve

The XML is the shape the shop's `nasluka-feeds` plugin already reads:

```xml
<products><item><sku/><price/><quantity/><availability/></item></products>
```

`availability` is `in_stock` / `out_of_stock`. Verified against the plugin's
own PHP `simplexml` parser.

## Publishing the result

The shop reads the XML over HTTP. Commit the generated files to this repo and
they are served from `raw.githubusercontent.com`, exactly as before — the only
change is that the files are produced on a desktop instead of by the Action.

```bash
git add results_filstar.csv filstar_xml_*.xml not_found_filstar.csv
git commit -m "Stock update $(date +%F)"
git push
```

Do not commit `.cache/` — it is already ignored.

## Worth knowing

The plugin refuses to apply a feed whose contents have stopped changing
(`Nasluka_Feeds_Sync::is_stale()`), so a run that silently stops updating will
not mark the catalogue sold out. It just goes quiet. Check the dates.

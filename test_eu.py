#!/usr/bin/env python3
"""Proefrun: kijkt of de AFM- en Zweedse insiderregisters automatisch op te halen zijn.
Schrijft alleen uitleg naar het logboek, verandert niets aan je gegevens."""
import csv, io, re, sys, urllib.request, urllib.error, urllib.parse
from html.parser import HTMLParser

UA = {"User-Agent": "Mozilla/5.0 (insider-radar proefrun)"}


def haal(url, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as e:
            return e.code, "", str(e).encode()
        except Exception as e:
            last = e
    return 0, "", str(last).encode()


def tekst(b):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", "replace")


print("=== AFM (Nederland) ===")
url = "https://www.afm.nl/export.aspx?type=0ee836dc-5520-459d-bcf4-a4a689de6614&format=csv"
st, ct, data = haal(url)
print("status", st, "type", ct, "bytes", len(data))
if st == 200:
    t = tekst(data)
    regels = t.splitlines()
    print("regels:", len(regels))
    print("kop:", regels[0][:400])
    for r in regels[1:4]:
        print("voorbeeld:", r[:400])
    sep = ";" if regels[0].count(";") > regels[0].count(",") else ","
    rijen = list(csv.reader(io.StringIO(t), delimiter=sep))
    kop = rijen[0]
    print("kolommen:", kop)
    for naam in ("Semiconductor", "BESI", "KPN", "Ahold", "ASML", "Adyen"):
        hits = [r for r in rijen[1:] if any(naam.lower() in c.lower() for c in r)]
        print(f"-- {naam}: {len(hits)} rijen; nieuwste voorbeelden:")
        for r in hits[:2]:
            print("   ", " | ".join(r)[:400])
else:
    print("antwoord:", tekst(data)[:300])

print()
print("=== Finansinspektionen (Zweden) ===")
basis = "https://marknadssok.fi.se/publiceringsklient/en-GB/Search?SearchFunctionType=Insyn&Utgivare=Volati"
for label, u in [
    ("zoekpagina", basis),
    ("export (button=export)", basis + "&button=export"),
    ("export (Export=true)", basis + "&Export=true"),
]:
    st, ct, data = haal(u)
    t = tekst(data)
    print(f"[{label}] status {st}, type {ct}, bytes {len(data)}")
    if "csv" in ct.lower() or "excel" in ct.lower() or "spreadsheet" in ct.lower() or (t[:200].count(";") > 3 and "<html" not in t[:300].lower()):
        print("  EXPORT LIJKT TE WERKEN. Eerste regels:")
        for r in t.splitlines()[:4]:
            print("   ", r[:400])
    else:
        rij_aantal = len(re.findall(r"<tr", t, re.I))
        print("  html, <tr>-regels:", rij_aantal)
        i = t.find("Volati")
        print("  fragment rond 'Volati':", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t[max(0, i - 200): i + 600]))[:500] if i >= 0 else "niet gevonden")
        links = re.findall(r'href="([^"]*(?:xport|xcel|csv)[^"]*)"', t, re.I)
        print("  mogelijke exportlinks:", links[:5])

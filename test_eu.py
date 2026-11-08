#!/usr/bin/env python3
"""Proefrun 2: bekijkt hoe de AFM-lijst, AFM-detailpagina's en de Zweedse tabel zijn opgebouwd.
Schrijft alleen uitleg naar het logboek."""
import re, urllib.request, urllib.error, html

UA = {"User-Agent": "Mozilla/5.0 (insider-radar proefrun)"}


def haal(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)


def kaal(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def rijen(t):
    uit = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S | re.I):
        cel = [kaal(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if cel:
            uit.append(cel)
    return uit


BASIS = "https://www.afm.nl/nl-nl/sector/registers/meldingenregisters/transacties-leidinggevenden-mar19-"
print("=== AFM lijstpagina ===")
st, t = haal(BASIS)
print("status", st, "bytes", len(t))
ids = re.findall(r"details\?id=([0-9A-Za-z\-]+)", t)
print("aantal detaillinks:", len(ids), "eerste:", ids[:3])
print("formuliervelden:", sorted(set(re.findall(r'name="([^"]+)"', t)))[:40])
for m in re.finditer(r"(?i)(pageindex|page=|__doPostBack|data-page|paging|pagina)", t):
    print("pagineringshint:", kaal(t[max(0, m.start() - 80): m.end() + 120])[:200])
    break
print("pagineringslinks:", re.findall(r'href="([^"]*[?&;](?:page|pagina|p)=[^"]*)"', t, re.I)[:5])
for r in rijen(t)[:4]:
    print("rij:", r)

print()
print("=== AFM andere pagina's / zoekterm proberen ===")
for naam, q in [("page=2", "?page=2"), ("pagina=2", "?pagina=2"), ("p=2", "?p=2"),
                ("zoekterm", "?zoekterm=BE+Semiconductor"), ("searchTerm", "?searchTerm=BE+Semiconductor"),
                ("datum", "?datumvan=2026-10-01&datumtot=2026-11-08")]:
    st2, t2 = haal(BASIS + q)
    ids2 = re.findall(r"details\?id=([0-9A-Za-z\-]+)", t2)
    r2 = rijen(t2)
    print(f"{naam}: status {st2}, detaillinks {len(ids2)}, eerste id {ids2[:1]}, eerste rij {r2[1] if len(r2) > 1 else None}")

print()
print("=== AFM detailpagina (eerste melding) ===")
if ids:
    st3, t3 = haal(BASIS + "/details?id=" + ids[0])
    print("status", st3)
    print(kaal(t3)[:1500])

print()
print("=== Zweden: tabel en paginering ===")
S = "https://marknadssok.fi.se/publiceringsklient/en-GB/Search?SearchFunctionType=Insyn&Utgivare=Volati"
st4, t4 = haal(S)
print("status", st4)
tab = rijen(t4)
print("rijen in tabel:", len(tab))
for r in tab[:4]:
    print("rij:", r)
print("links met page:", re.findall(r'href="([^"]*(?:[?&;]page|Page)[^"]*)"', t4)[:6])
st5, t5 = haal(S + "&Page=2")
tab5 = rijen(t5)
print("Page=2: rijen", len(tab5), "eerste", tab5[1] if len(tab5) > 1 else None)

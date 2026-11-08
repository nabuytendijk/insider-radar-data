#!/usr/bin/env python3
"""Proefrun 3: zoekt de bouwstenen van de AFM-lijst, AFM-detailpagina en het Zweedse zoekformulier.
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


BASIS = "https://www.afm.nl/nl-nl/sector/registers/meldingenregisters/transacties-leidinggevenden-mar19-"
print("=== AFM: opbouw van de lijst ===")
st, t = haal(BASIS)
i = t.find('id="registers_register-paged-list_div"')
print("lijstblok:", re.sub(r"\s+", " ", t[i:i + 900]))
j = t.find("details?id=")
print()
print("eerste lijstregel (HTML):", re.sub(r"\s+", " ", t[max(0, j - 500): j + 700]))
print()
print("scripts:", re.findall(r'<script[^>]+src="([^"]+)"', t)[:15])
for m in re.finditer(r"(?i)(/api/|ajax|handler|\.ashx|fetch\(|data-url|data-endpoint)", t):
    print("hint:", re.sub(r"\s+", " ", t[max(0, m.start() - 100): m.end() + 200])[:300])

print()
print("=== AFM: detailpagina ===")
ids = re.findall(r"details\?id=([0-9A-Za-z\-]+)", t)
st3, t3 = haal(BASIS + "/details?id=" + ids[0])
k = t3.find("Soort transactie")
if k < 0:
    k = t3.find("Meldingsplichtige")
print("zoekpositie:", k)
print("blok:", re.sub(r"\s+", " ", t3[max(0, k - 1500): k + 2500]))

print()
print("=== Zweden: formulier ===")
S = "https://marknadssok.fi.se/publiceringsklient/en-GB/Search?SearchFunctionType=Insyn"
st4, t4 = haal(S)
print("formulier:", re.findall(r'<form[^>]*>', t4)[:3])
print("invoervelden:", re.findall(r'<(?:input|select)[^>]*name="([^"]+)"', t4))
for naam in ("Utgivare", "Issuer", "issuer", "utgivare", "IssuerName"):
    st5, t5 = haal(S + "&button=search&" + naam + "=Volati")
    kolom = re.findall(r"<td[^>]*>(.*?)</td>", t5, re.S)
    uitgevers = sorted(set(kaal(c) for n, c in enumerate(kolom) if n % 16 == 1))
    print(f"{naam}: status {st5}, uitgevers in resultaat: {uitgevers[:6]}")

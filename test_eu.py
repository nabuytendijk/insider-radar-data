#!/usr/bin/env python3
"""Proefrun 4: probeert de registers van Frankrijk (AMF), Duitsland (BaFin), Zwitserland (SIX)
en Finland (Consti) te bereiken. Schrijft alleen uitleg naar het logboek."""
import json, re, html, urllib.request, urllib.error

UA = {"User-Agent": "Mozilla/5.0 (insider-radar proefrun)", "Accept": "application/json, text/html, */*"}


def haal(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, "", ""
    except Exception as e:
        return 0, "", str(e)


def kaal(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def probeer(label, url, toon=500):
    st, ct, t = haal(url)
    print(f"[{label}] status {st}, type {ct[:40]}, {len(t)} tekens")
    print("   begin:", re.sub(r"\s+", " ", t[:toon]))
    return st, ct, t


print("=== FRANKRIJK (AMF) ===")
B = "https://bdif.amf-france.org/back/api/v1/informations"
for q in ["", "?From=0&Size=3", "?TypesInformation=BDIF&From=0&Size=3", "?Texte=Danone&From=0&Size=3",
          "?TypesInformation=BDIF&TypesDocument=DD&From=0&Size=3"]:
    st, ct, t = probeer("amf " + q, B + q, 600)
    try:
        j = json.loads(t)
        print("   json-sleutels:", list(j.keys())[:10] if isinstance(j, dict) else type(j))
    except Exception:
        pass

print()
print("=== DUITSLAND (BaFin) ===")
for u in ["https://portal.mvp.bafin.de/database/DealingsInfo/",
          "https://portal.mvp.bafin.de/database/DealingsInfo/sucheForm.do",
          "https://portal.mvp.bafin.de/database/DealingsInfo/sucheForm.do?emittentName=Munich"]:
    st, ct, t = probeer("bafin", u, 300)
    if st == 200:
        print("   formuliervelden:", re.findall(r'name="([^"]+)"', t)[:25])
        print("   links met export/csv/xls:", re.findall(r'href="([^"]*(?:xport|csv|xls)[^"]*)"', t, re.I)[:5])

print()
print("=== ZWITSERLAND (SIX Exchange Regulation) ===")
for u in ["https://disclosure.six-exchange-regulation.com/obligations/management_transaction/ddeal/disclosure_list_en",
          "https://www.ser-ag.com/en/resources/notifications-market-participants/management-transactions.html"]:
    st, ct, t = probeer("six", u, 300)
    if st == 200:
        print("   formuliervelden:", re.findall(r'name="([^"]+)"', t)[:25])
        print("   links met export/csv/xls/api/json:", re.findall(r'(?:href|src)="([^"]*(?:xport|csv|xls|api|json)[^"]*)"', t, re.I)[:8])
        i = t.find("Nestl")
        print("   fragment bij Nestlé:", kaal(t[max(0, i - 200): i + 400]) if i >= 0 else "niet gevonden")

print()
print("=== FINLAND (Consti) ===")
st, ct, t = probeer("inderes", "https://www.inderes.fi/en/releases/consti-plc-managers-transactions-21", 200)
if st == 200:
    print("   tekst:", kaal(t)[:1500])
for u in ["https://api.news.eu.nasdaq.com/news/query.action?globalGroup=exchangeNotice&displayLanguage=en&timeZone=CET&limit=5&start=0&company=Consti%20Plc&countryCode=fi&dateMask=yyyy-MM-dd%20HH:mm:ss&globalName=NordicAllMarkets&cnSearch=managers",
          "https://www.inderes.fi/en/releases"]:
    probeer("finland", u, 500)

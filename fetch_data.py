#!/usr/bin/env python3
"""Haalt dagkoersen (Alpha Vantage) en insidertransacties (SEC EDGAR Form 4) op.

Schrijft naar data/koersen.json en data/transacties_us.json.
Alleen standaardbibliotheek. Sleutels komen uit omgevingsvariabelen:
  ALPHAVANTAGE_KEY   je Alpha Vantage-sleutel (GitHub-secret)
  SEC_USER_AGENT     naam + contactadres voor de SEC, bv. "Jouw Naam jouw@adres" (GitHub-secret)
Gebruik:  python fetch_data.py            haalt alles op
          python fetch_data.py --selftest test van de Form 4-lezer, zonder internet
"""
import json, os, sys, time, datetime as dt
import urllib.request, urllib.error
import xml.etree.ElementTree as ET

TICKERS = {  # ticker: naam
    "MSFT": "Microsoft", "GOOGL": "Alphabet", "INTC": "Intel",
    "AAPL": "Apple", "NVDA": "Nvidia", "AMZN": "Amazon", "MCD": "McDonald's",
    "AMD": "AMD", "AVGO": "Broadcom", "MU": "Micron", "GEV": "GE Vernova",
    "TSM": "TSMC",  # TSMC meldt niet via Form 4: alleen koersen
}
EU = {  # ticker: Yahoo-code; koersen in lokale valuta (VOLO/CIBUS in SEK, NESN in CHF)
    "BESI": "BESI.AS", "VOLO": "VOLO.ST", "KPN": "KPN.AS", "AD": "AD.AS",
    "ABN": "ABN.AS", "ASML": "ASML.AS", "ASRNL": "ASRNL.AS", "INGA": "INGA.AS",
    "PHIA": "PHIA.AS", "SHELL": "SHELL.AS", "SIFG": "SIFG.AS", "UNA": "UNA.AS",
    "WHA": "WHA.AS", "BN": "BN.PA", "HNR1": "HNR1.DE", "MUV2": "MUV2.DE",
    "NESN": "NESN.SW", "SAN": "SAN.PA", "HO": "HO.PA", "TTE": "TTE.PA",
    "SESG": "SESG.PA", "ETL": "ETL.PA", "CIBUS": "CIBUS.ST", "CONSTI": "CONSTI.HE",
    "ADYEN": "ADYEN.AS", "ENR": "ENR.DE", "ASM": "ASM.AS", "SU": "SU.PA",
}
VANAF = {"VOLO": "2026-06-08"}  # eerdere koersen zijn niet vergelijkbaar (splitsing/emissie)
DAGEN_EU = 400             # kalenderdagen koershistorie voor de Europese aandelen
DAGEN_TERUG = 365          # hoe ver terug Form 4-meldingen worden meegenomen
AV_PAUZE = 15              # seconden tussen Alpha Vantage-verzoeken (gratis limiet is laag)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def get(url, headers=None, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < tries - 1:
                time.sleep(5 * (i + 1)); continue
            raise
    raise RuntimeError("niet gelukt: " + url)


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


# ---------- koersen ----------
def fetch_prices(key):
    pad = os.path.join(OUT, "koersen.json")
    store = {t: {d: c for d, c in v} for t, v in load(pad, {}).items() if t in TICKERS}
    for n, t in enumerate(TICKERS):
        if n:
            time.sleep(AV_PAUZE)
        url = ("https://www.alphavantage.co/query?function=TIME_SERIES_DAILY"
               f"&symbol={t}&outputsize=compact&apikey={key}")
        data = json.loads(get(url))
        serie = data.get("Time Series (Daily)")
        if not serie:
            # limiet- of sleutelmelding staat in 'Note', 'Information' of 'Error Message'
            print(f"[koers] {t}: geen data ->", {k: v for k, v in data.items() if k != 'Meta Data'}, file=sys.stderr)
            continue
        d = store.setdefault(t, {})
        for datum, v in serie.items():
            d[datum] = float(v["4. close"])
        print(f"[koers] {t}: {len(serie)} dagen opgehaald, {len(d)} in archief")
    uit = load(pad, {})  # bewaar ook de Europese reeksen die er al staan
    uit.update({t: sorted(d.items()) for t, d in store.items()})
    save(pad, uit)


# ---------- Europese koersen (zonder sleutel) ----------
def parse_stooq(tekst, vanaf):
    """CSV 'Date,Open,High,Low,Close,Volume' -> [(datum, slot)]"""
    regels = tekst.strip().splitlines()
    if not regels or not regels[0].lower().startswith("date"):
        raise ValueError("geen CSV: " + tekst[:80].replace("\n", " "))
    uit = []
    for r in regels[1:]:
        k = r.split(",")
        if len(k) >= 5 and k[0] >= vanaf:
            uit.append((k[0], float(k[4])))
    return uit


def parse_yahoo(tekst, vanaf):
    res = json.loads(tekst)["chart"]["result"][0]
    sloten = res["indicators"]["quote"][0]["close"]
    uit = []
    for ts, c in zip(res["timestamp"], sloten):
        d = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()
        if c is not None and d >= vanaf:
            uit.append((d, round(float(c), 4)))
    return uit


def fetch_eu_prices():
    pad = os.path.join(OUT, "koersen.json")
    store = load(pad, {})
    vanaf = (dt.date.today() - dt.timedelta(days=DAGEN_EU)).isoformat()
    for t, yahoo in EU.items():
        v = max(vanaf, VANAF.get(t, ""))
        try:
            u = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo}?range=2y&interval=1d"
            punten = parse_yahoo(get(u, {"User-Agent": "Mozilla/5.0"}).decode("utf-8"), v)
        except Exception as e:
            print(f"[eu-koers] {t}: Yahoo mislukt ({e})", file=sys.stderr); continue
        if len(punten) < 5:
            print(f"[eu-koers] {t}: geen koersen gevonden", file=sys.stderr); continue
        d = {x[0]: x[1] for x in store.get(t, []) if x[0] >= v}
        d.update(dict(punten))
        store[t] = sorted(d.items())
        print(f"[eu-koers] {t}: {len(punten)} dagen, {len(store[t])} in archief, laatste {store[t][-1]}")
        time.sleep(1)
    save(pad, store)


# ---------- Form 4 ----------
def _txt(el, path):
    x = el.find(path)
    return x.text.strip() if x is not None and x.text else None


def parse_form4(xml_bytes, ticker, naam, datum_melding, acc, cik=None):
    """Geeft rijen voor open-markt aankopen (P) en verkopen (S) in het dashboardformaat."""
    root = ET.fromstring(xml_bytes)
    rij = []
    uitgever = _txt(root, "issuer/issuerCik")
    if cik and uitgever and int(uitgever) != int(cik):
        return []  # melding gaat over een ander bedrijf (bv. een beleggingsfonds van het concern), niet over dit aandeel
    eigenaar = root.find("reportingOwner")
    persoon = _txt(eigenaar, "reportingOwnerId/rptOwnerName") or "onbekend"
    rel = eigenaar.find("reportingOwnerRelationship") if eigenaar is not None else None
    rol = "Bestuur"
    if rel is not None:
        titel = _txt(rel, "officerTitle")
        if _txt(rel, "isOfficer") in ("1", "true") and titel:
            rol = titel
        elif _txt(rel, "isTenPercentOwner") in ("1", "true"):
            rol = "Aandeelhouder >10%"
        elif _txt(rel, "isDirector") in ("1", "true"):
            rol = "Bestuurder / commissaris"
    for i, tx in enumerate(root.findall("nonDerivativeTable/nonDerivativeTransaction")):
        code = _txt(tx, "transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue  # alleen echte aankopen en verkopen op de markt
        datum = _txt(tx, "transactionDate/value") or datum_melding
        aantal = float(_txt(tx, "transactionAmounts/transactionShares/value") or 0)
        prijs = _txt(tx, "transactionAmounts/transactionPricePerShare/value")
        if not aantal or prijs is None:
            continue
        rij.append({
            "id": f"{ticker}-{datum[:10]}-{acc}-{i}",
            "ticker": ticker, "naam": naam, "status": "Watchlist",
            "datum": datum[:10], "persoon": persoon, "rol": rol,
            "type": "koop" if code == "P" else "verkoop",
            "aantal": int(aantal), "koers": round(float(prijs), 4), "valuta": "USD",
            "bron": "SEC EDGAR Form 4", "controle": "nee", "toelichting": "",
        })
    return rij


def fetch_form4(ua):
    h = {"User-Agent": ua, "Accept-Encoding": "identity"}
    ciks = {v["ticker"]: str(v["cik_str"]).zfill(10)
            for v in json.loads(get("https://www.sec.gov/files/company_tickers.json", h)).values()}
    grens = (dt.date.today() - dt.timedelta(days=DAGEN_TERUG)).isoformat()
    pad = os.path.join(OUT, "transacties_us.json")
    bestaand = {r["id"]: r for r in load(pad, []) if not r.get("persoon", "").startswith("GV 20") and r.get("ticker") != "TSM"}  # oude foutieve GV-regels weg; TSMC heeft geen Form 4
    for t, naam in TICKERS.items():
        if t == "TSM":
            continue  # TSMC is buitenlandse emittent: geen Form 4, alleen koersen
        cik = ciks.get(t)
        if not cik:
            print(f"[form4] {t}: CIK niet gevonden", file=sys.stderr); continue
        sub = json.loads(get(f"https://data.sec.gov/submissions/CIK{cik}.json", h))["filings"]["recent"]
        nieuw = 0
        for form, acc, datum, doc in zip(sub["form"], sub["accessionNumber"], sub["filingDate"], sub["primaryDocument"]):
            if form != "4" or datum < grens:
                continue
            accn = acc.replace("-", "")
            if any(k.startswith(f"{t}-") and f"-{accn}-" in k for k in bestaand):
                continue  # al verwerkt
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{doc.split('/')[-1]}"
            time.sleep(0.15)  # SEC staat max 10 verzoeken per seconde toe
            try:
                for r in parse_form4(get(url, h), t, naam, datum, accn, cik):
                    bestaand[r["id"]] = r; nieuw += 1
            except Exception as e:
                print(f"[form4] {t} {acc}: overgeslagen ({e})", file=sys.stderr)
        print(f"[form4] {t}: {nieuw} nieuwe aankopen/verkopen")
    save(pad, sorted(bestaand.values(), key=lambda r: r["datum"], reverse=True))


def selftest():
    xml = b"""<ownershipDocument><reportingOwner><reportingOwnerId><rptOwnerName>Voorbeeld Persoon</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>CFO</officerTitle></reportingOwnerRelationship></reportingOwner>
    <nonDerivativeTable>
    <nonDerivativeTransaction><transactionDate><value>2026-01-02</value></transactionDate><transactionCoding><transactionCode>S</transactionCode></transactionCoding>
    <transactionAmounts><transactionShares><value>100</value></transactionShares><transactionPricePerShare><value>10.5</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction>
    <nonDerivativeTransaction><transactionDate><value>2026-01-02</value></transactionDate><transactionCoding><transactionCode>A</transactionCode></transactionCoding>
    <transactionAmounts><transactionShares><value>50</value></transactionShares><transactionPricePerShare><value>0</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction>
    </nonDerivativeTable></ownershipDocument>"""
    r = parse_form4(xml, "TEST", "Test", "2026-01-03", "000")
    assert len(r) == 1 and r[0]["type"] == "verkoop" and r[0]["aantal"] == 100 and r[0]["rol"] == "CFO", r
    print("selftest ok:", r[0])
    assert parse_stooq("Date,Open,High,Low,Close,Volume\n2026-01-02,1,2,0.5,1.5,100\n2025-01-01,1,1,1,9,1", "2026-01-01") == [("2026-01-02", 1.5)]
    y = '{"chart":{"result":[{"timestamp":[1767312000,1767398400],"indicators":{"quote":[{"close":[10.5,null]}]}}]}}'
    assert parse_yahoo(y, "2026-01-01") == [("2026-01-02", 10.5)], parse_yahoo(y, "2026-01-01")
    print("selftest koersen ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest(); sys.exit(0)
    key, ua = os.environ.get("ALPHAVANTAGE_KEY"), os.environ.get("SEC_USER_AGENT")
    if not key or not ua:
        sys.exit("Zet ALPHAVANTAGE_KEY en SEC_USER_AGENT als omgevingsvariabelen (GitHub-secrets).")
    fetch_form4(ua)
    fetch_prices(key)
    fetch_eu_prices()

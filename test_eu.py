"""Proefrun 5: AMF (FR), BaFin (DE), Consti (FI), Nasdaq-nieuws (FI)."""
import json, re, urllib.request, urllib.parse, html

UA = {"User-Agent": "Mozilla/5.0 (insider-radar proef)", "Accept": "*/*"}


def get(url, data=None, headers=None):
    h = dict(UA)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.status, r.read().decode("utf-8", "replace")


def kop(t):
    print("\n" + "=" * 70 + "\n" + t + "\n" + "=" * 70)


def tekst(h):
    h = re.sub(r"(?s)<(script|style).*?</\1>", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(h)).strip()


# ---------- 1. AMF Frankrijk ----------
kop("AMF: structuur")
base = "https://bdif.amf-france.org/back/api/v1/informations"
try:
    s, b = get(base + "?From=0&Size=3")
    j = json.loads(b)
    print("total:", j.get("total"))
    aggs = j.get("aggregations")
    print("aggregations type:", type(aggs).__name__)
    if isinstance(aggs, dict):
        for k, v in aggs.items():
            print("AGG", k, json.dumps(v, ensure_ascii=False)[:600])
    elif isinstance(aggs, list):
        for a in aggs[:12]:
            print("AGG", json.dumps(a, ensure_ascii=False)[:600])
    res = j.get("result")
    print("result type:", type(res).__name__)
    items = res if isinstance(res, list) else (res or {}).get("hits") or []
    for it in items[:2]:
        print("ITEM", json.dumps(it, ensure_ascii=False)[:1500])
except Exception as e:
    print("FOUT", e)

kop("AMF: zoeken op Danone met verschillende parameternamen")
for q in ["Texte=Danone", "texte=Danone", "Search=Danone", "Query=Danone",
          "Keyword=Danone", "q=Danone", "Emetteur=Danone", "Societe=Danone"]:
    try:
        s, b = get(base + "?" + q + "&From=0&Size=2")
        j = json.loads(b)
        print(q, "-> total", j.get("total"), "len", len(b))
    except Exception as e:
        print(q, "FOUT", e)

# ---------- 2. BaFin Duitsland ----------
kop("BaFin: formulier insturen")
try:
    url = "https://portal.mvp.bafin.de/database/DealingsInfo/sucheForm.do"
    s, f = get(url)
    m = re.search(r"(?is)<form[^>]*>", f)
    print("form-tag:", m.group(0) if m else None)
    for inp in re.findall(r"(?is)<input[^>]*>", f):
        print("INPUT", inp[:200])
    act = re.search(r'(?is)<form[^>]*action="([^"]*)"', f)
    action = urllib.parse.urljoin(url, act.group(1)) if act else url
    print("action:", action)
    for naam in ["Münchener", "Munich"]:
        for methode in ["POST", "GET"]:
            par = {"emittentName": naam, "emittentIsin": "", "meldepflichtigerName": "",
                   "zeitraum": "0", "zeitraumVon": "01.01.2026", "zeitraumBis": "08.11.2026",
                   "emittentButton": "Suche Emittent"}
            q = urllib.parse.urlencode(par).encode()
            try:
                if methode == "POST":
                    s, r = get(action, data=q, headers={"Content-Type": "application/x-www-form-urlencoded"})
                else:
                    s, r = get(action + "?" + q.decode())
                print("\n", naam, methode, s, len(r))
                print(tekst(r)[:1500])
                for l in re.findall(r'(?i)href="([^"]*(?:csv|xls|export|download|Detail)[^"]*)"', r)[:8]:
                    print("LINK", l)
            except Exception as e:
                print(naam, methode, "FOUT", e)
except Exception as e:
    print("FOUT", e)

# ---------- 3. Consti release ----------
kop("Consti: releasetekst uit Next.js-data")
try:
    s, p = get("https://www.inderes.fi/en/releases/consti-plc-managers-transactions-21")
    m = re.search(r'(?s)<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', p)
    if m:
        d = json.loads(m.group(1))
        tot = []

        def loop(x):
            if isinstance(x, dict):
                for v in x.values():
                    loop(v)
            elif isinstance(x, list):
                for v in x:
                    loop(v)
            elif isinstance(x, str) and len(x) > 200:
                tot.append(x)
        loop(d)
        for t in tot[:3]:
            print("TEKST", tekst(t)[:2500])
            print("---")
    else:
        print("geen __NEXT_DATA__; zoek tekst in de pagina")
        print("push-chunks:", len(re.findall(r"self\.__next_f\.push", p)))
        for mm in re.findall(r"(?i)(Nature of transaction.{0,500})", p)[:2]:
            print(mm)
except Exception as e:
    print("FOUT", e)

# ---------- 4. Nasdaq-nieuws ----------
kop("Nasdaq-nieuws: parametervarianten")
n = "https://api.news.eu.nasdaq.com/news/query.action"
varianten = [
    "countResults=true&globalGroup=exchangeNotice&displayLanguage=en&timeZone=CET&dateMask=yyyy-MM-dd+HH%3Amm%3Ass&limit=5&start=0&dir=DESC&globalName=NordicAllMarkets&company=Consti&callback=cb",
    "countResults=true&globalGroup=exchangeNotice&displayLanguage=en&timeZone=CET&dateMask=yyyy-MM-dd+HH%3Amm%3Ass&limit=5&start=0&dir=DESC&globalName=NordicAllMarkets&freeText=Consti+managers&callback=cb",
    "globalGroup=exchangeNotice&displayLanguage=en&limit=5&start=0&dir=DESC&globalName=NordicAllMarkets&market=Nasdaq+Helsinki&callback=cb",
]
for v in varianten:
    try:
        s, r = get(n + "?" + v, headers={"Referer": "https://www.nasdaq.com/"})
        print(s, len(r), r[:700].replace("\n", " "))
    except Exception as e:
        print("FOUT", e)

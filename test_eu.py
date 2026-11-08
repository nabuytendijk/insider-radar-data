"""Proefrun 6: AMF-filters, BaFin-detailpagina, Nasdaq managers' transactions."""
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


# ---------- 1. AMF ----------
kop("AMF: sleutels van typesInformation")
base = "https://bdif.amf-france.org/back/api/v1/informations"
try:
    s, b = get(base + "?From=0&Size=1")
    j = json.loads(b)
    for bk in j["aggregations"]["typesInformation"]["buckets"]:
        print("TYPE", json.dumps(bk.get("key")), bk.get("docCount"))
except Exception as e:
    print("FOUT", e)

kop("AMF: filter op type")
for q in ["TypesInformation=DD", "TypesInformation=DIRIGEANT", "TypesInformation=DDD",
          "TypesInformation=DI", "TypesInformation=FT", "TypesOperation=ACQUISITION",
          "TypesDocument=DECLARATION_DIRIGEANT"]:
    try:
        s, b = get(base + "?" + q + "&From=0&Size=2")
        j = json.loads(b)
        print(q, "-> total", j.get("total"))
        if j.get("total") and "DD" in q or "DIRIG" in q:
            for it in j["result"][:2]:
                print("  ITEM", json.dumps(it, ensure_ascii=False)[:1200])
    except Exception as e:
        print(q, "FOUT", e)

# ---------- 2. BaFin ----------
kop("BaFin: ruwe HTML van de eerste resultaatrij + detail")
try:
    u = "https://portal.mvp.bafin.de/database/DealingsInfo/sucheForm.do"
    par = urllib.parse.urlencode({"emittentIsin": "DE0008430026", "emittentName": "",
                                  "meldepflichtigerName": "", "zeitraum": "0",
                                  "zeitraumVon": "", "zeitraumBis": "",
                                  "emittentButton": "Suche Emittent"}).encode()
    s, r = get(u, data=par, headers={"Content-Type": "application/x-www-form-urlencoded"})
    print("status", s, "len", len(r), "tekst:", tekst(r)[-700:])
    i = r.find("Kerner")
    if i < 0:
        i = r.find("<table")
    print("RAW", r[max(0, i - 700):i + 900])
    links = re.findall(r'(?i)href="([^"]*)"', r)
    for l in links:
        if re.search(r"(?i)detail|transaktion|geschaeft|Eigen|id=", l):
            print("LINK", l)
    for l in re.findall(r'(?i)(?:onclick|href)="[^"]*(?:detail|Detail)[^"]*"', r)[:5]:
        print("CLICK", l)
except Exception as e:
    print("FOUT", e)

# ---------- 3. Nasdaq ----------
kop("Nasdaq: managers' transactions voor Consti")
n = "https://api.news.eu.nasdaq.com/news/query.action"
bas = ("countResults=true&globalGroup=exchangeNotice&displayLanguage=en&timeZone=CET"
       "&dateMask=yyyy-MM-dd+HH%3Amm%3Ass&limit=50&start=0&dir=DESC&globalName=NordicAllMarkets&callback=cb")
try:
    for extra in ["&freeText=Consti+Managers", "&freeText=Consti&cnsCategory=Managers%27+Transactions",
                  "&company=Consti+Oyj", "&freeText=Consti"]:
        s, r = get(n + "?" + bas + extra, headers={"Referer": "https://www.nasdaq.com/"})
        j = json.loads(r[r.index("(") + 1:r.rindex(")")])
        items = j["results"]["item"]
        mt = [i for i in items if "Managers" in i.get("cnsCategory", "")]
        print(extra, "-> items", len(items), "managers", len(mt))
        for i in mt[:4]:
            print("   ", i["releaseTime"], i["headline"], "|", i["messageUrl"])
        if mt:
            s2, v = get(mt[0]["messageUrl"])
            print("VIEW", s2, len(v), tekst(v)[:900])
            break
except Exception as e:
    print("FOUT", e)

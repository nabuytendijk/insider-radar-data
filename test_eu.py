"""Proefrun 8: BaFin CSV-export en transactiedetail."""
import re, html, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (insider-radar proef)"}
B = "https://portal.mvp.bafin.de/database/DealingsInfo/"


def tekst(h):
    h = re.sub(r"(?s)<(script|style).*?</\1>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
op.addheaders = list(UA.items())
form = {"emittentIsin": "DE0008430026", "emittentName": "", "meldepflichtigerName": "", "zeitraum": "0",
        "zeitraumVon": "", "zeitraumBis": "", "emittentButton": "Suche Emittent"}
r = op.open(B + "sucheForm.do", urllib.parse.urlencode(form).encode(), timeout=40).read().decode("utf-8", "replace")
print("=== links in de buurt van 'Exportoptionen'")
i = r.find("Exportoptionen")
print(r[max(0, i - 200):i + 700])
exp = [html.unescape(l) for l in re.findall(r'href="([^"]*6578706f7274[^"]*)"', r)]
print("EXPORTLINKS", exp)
for l in exp[:2]:
    try:
        d = op.open(urllib.parse.urljoin(B + "sucheForm.do", l), timeout=40).read().decode("utf-8", "replace")
        print("=== EXPORT", l[-60:], len(d))
        print(d[:1800])
    except Exception as e:
        print("FOUT", e)

print("=== detailpagina: links")
d = op.open(B + "ergebnisListe.do?cmd=loadMeldepflichtigeAction&emittentBafinId=40001467&meldungId=34605", timeout=40).read().decode("utf-8", "replace")
for l in re.findall(r'href="([^"]*)"', d):
    if "Action" in l or "Geschaeft" in l or "meldung" in l.lower():
        print("LINK", html.unescape(l))
i = d.find("Malherbe")
print(d[max(0, i - 400):i + 400])


print("=== Consti-debug")
import json
n = "https://api.news.eu.nasdaq.com/news/query.action"
bas = ("countResults=true&globalGroup=exchangeNotice&displayLanguage=en&timeZone=CET"
       "&dateMask=yyyy-MM-dd+HH%3Amm%3Ass&limit=50&start=0&dir=DESC&globalName=NordicAllMarkets&callback=cb&freeText=Consti+Managers")
rq = urllib.request.Request(n + "?" + bas, headers=UA)
rr = urllib.request.urlopen(rq, timeout=40).read().decode()
its = json.loads(rr[rr.index("(") + 1:rr.rindex(")")])["results"]["item"]
mt = [i for i in its if "Managers" in i.get("cnsCategory", "") and "consti" in i["headline"].lower()]
print("aantal", len(mt))
for i in mt[:13]:
    v = urllib.request.urlopen(urllib.request.Request(i["messageUrl"], headers=UA), timeout=40).read().decode("utf-8", "replace")
    t = tekst(v)
    k = t.find("Person subject")
    print("---", i["releaseTime"], i["headline"])
    print(t[k:k + 1100])

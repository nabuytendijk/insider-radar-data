"""Proefrun 9: Zwitserland (SIX Exchange Regulation), managementtransacties."""
import json, re, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (insider-radar proef)", "Accept": "*/*"}


def get(url, headers=None):
    h = dict(UA)
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40) as r:
        return r.status, r.read().decode("utf-8", "replace")


def kop(t):
    print("\n" + "=" * 70 + "\n" + t + "\n" + "=" * 70)


kop("Pagina en scripts zoeken naar de data-API")
pagina = "https://www.ser-ag.com/en/resources/notifications-market-participants/management-transactions.html"
gevonden = set()
try:
    s, h = get(pagina)
    print("pagina", s, len(h))
    for m in re.findall(r'(?:src|href)="([^"]+\.(?:js|json)[^"]*)"', h):
        print("SCRIPT", m)
        gevonden.add(urllib.parse.urljoin(pagina, m))
    for m in re.findall(r'[^"\s]*(?:sheldon|management_transactions|managementTransactions)[^"\s<]*', h)[:20]:
        print("VERWIJZING", m)
except Exception as e:
    print("FOUT", e)

kop("In de scripts zoeken")
for u in list(gevonden)[:25]:
    try:
        s, js = get(u)
        for m in set(re.findall(r'["\'`]([^"\'`\s]*(?:sheldon|management_transactions|managementTransactions|overview\.json)[^"\'`\s]*)', js)):
            print(u.split("/")[-1][:40], "->", m[:200])
    except Exception as e:
        print(u[-60:], "FOUT", e)

kop("Gokken op de API")
b = "https://www.ser-ag.com/sheldon/management_transactions/v1/"
for pad in ["overview.json?pageSize=3&pageNumber=0&sortAttribute=byDate&sortOrder=desc",
            "overview.json?pageSize=3&pageNumber=0",
            "overview.json",
            "csv.xlsx", "overview.csv"]:
    try:
        s, r = get(b + pad)
        print(pad, "->", s, len(r), r[:600].replace("\n", " "))
    except Exception as e:
        print(pad, "FOUT", e)

"""Proefrun 10: SIX Exchange Regulation overview.json - velden en filters (Nestlé)."""
import json, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (insider-radar proef)", "Accept": "application/json"}
B = "https://www.ser-ag.com/sheldon/management_transactions/v1/"


def get(q):
    with urllib.request.urlopen(urllib.request.Request(B + q, headers=UA), timeout=40) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


print("=== volledig voorbeeld")
j = get("overview.json?pageSize=2&pageNumber=0")
print(json.dumps(j["itemList"][0], indent=1, ensure_ascii=False))
print("sleutels van antwoord:", [k for k in j])

print("=== issuers.json")
try:
    iss = get("issuers.json")
    print(json.dumps(iss, ensure_ascii=False)[:600])
    lst = iss.get("itemList") or iss.get("issuers") or []
    for x in lst:
        if "nestl" in json.dumps(x).lower():
            print("NESTLE", x)
except Exception as e:
    print("FOUT", e)

print("=== filters op Nestlé (ISIN CH0038863350)")
for q in ["isin=CH0038863350", "ISIN=CH0038863350", "issuerId=NESTLE", "notificationSubmitterId=NESTLE",
          "notificationSubmitter=Nestl%C3%A9+SA", "issuer=NESTLE", "issuerFilter=NESTLE", "search=Nestle"]:
    try:
        j = get("overview.json?pageSize=5&pageNumber=0&" + q)
        l = j["itemList"]
        print(q, "-> totaal", j["totalCount"], "|", [(i["notificationSubmitter"], i["transactionDate"], i["buySellIndicator"]) for i in l[:3]])
    except Exception as e:
        print(q, "FOUT", e)

print("=== paginering en grootte")
for q in ["pageSize=100&pageNumber=0", "pageSize=100&pageNumber=1"]:
    j = get("overview.json?" + q)
    print(q, len(j["itemList"]), j["itemList"][0]["transactionDate"], j["itemList"][-1]["transactionDate"])

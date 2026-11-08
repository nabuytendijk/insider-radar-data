"""Proefrun 11: Nestlé-meldingen uit SIX Exchange Regulation (pagineren en lokaal filteren)."""
import collections, json, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (insider-radar proef)", "Accept": "application/json"}
B = "https://www.ser-ag.com/sheldon/management_transactions/v1/"


def get(q):
    with urllib.request.urlopen(urllib.request.Request(B + q, headers=UA), timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


alle = []
for p in range(0, 25):
    l = get(f"overview.json?pageSize=100&pageNumber={p}")["itemList"]
    if not l:
        break
    alle += l
print("opgehaald:", len(alle), "van", alle[-1]["transactionDate"], "tot", alle[0]["transactionDate"])
print("codes buySell:", collections.Counter(i["buySellIndicator"] for i in alle))
print("codes securityType:", collections.Counter(i["securityTypeCode"] for i in alle))
print("codes functie:", collections.Counter(i["obligorFunctionCode"] for i in alle))
print("codes related:", collections.Counter(i["obligorRelatedPartyInd"] for i in alle))
print("namen met 'nestl':", {(i["notificationSubmitter"], i["notificationSubmitterId"], i["ISIN"]) for i in alle if "nestl" in i["notificationSubmitter"].lower()})
print("=== Nestlé (ISIN CH0038863350)")
for i in alle:
    if i["ISIN"] == "CH0038863350":
        print(json.dumps({k: i[k] for k in ("transactionDate", "buySellIndicator", "securityTypeCode", "securityDescription",
              "transactionSize", "transactionAmountPerSecurityCHF", "transactionAmountCHF", "obligorFunctionCode",
              "obligorRelatedPartyInd", "transactionConditions", "notificationId")}, ensure_ascii=False))
print("=== voorbeeld per securityTypeCode")
gezien = set()
for i in alle:
    c = i["securityTypeCode"]
    if c not in gezien:
        gezien.add(c)
        print(c, i["notificationSubmitter"], i["transactionSize"], i["transactionAmountPerSecurityCHF"], repr(i["securityDescription"]))

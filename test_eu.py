"""Proefrun 14: register Bestuurders en commissarissen (art. 5:48 Wft).
Wat staat er in de velden Voorposities/Wijzigingen/Naposities, en hoe is een detailpagina opgebouwd?
Alleen lezen, schrijft niets weg."""
import re, html, collections, datetime as dt, urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (insider-radar proef)"}
EXP = "https://www.afm.nl/export.aspx?format=xml&type=1b934036-12ad-4950-9773-31361d5adbd9"
DET = "https://www.afm.nl/nl-nl/sector/registers/meldingenregisters/bestuurders-commissarissen/details?id="
ONZE = {"ABN AMRO Bank NV", "ASM International N.V.", "ASML Holding N.V.", "ASR Nederland N.V.", "Adyen N.V.",
        "BE Semiconductor Industries N.V.", "ING Groep N.V.", "Koninklijke Ahold Delhaize N.V.",
        "Koninklijke KPN N.V.", "Koninklijke Philips N.V.", "Sif Holding N.V.", "Wereldhave N.V."}
GRENS = dt.date.today() - dt.timedelta(days=400)


def haal(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=180) as r:
        return r.read()


def kaal(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


root = ET.fromstring(haal(EXP))
items = list(root)
d = lambda x: dt.datetime.strptime(x.findtext("DatumMeldingsplicht").strip(), "%m/%d/%Y").date()
onze = [x for x in items if (x.findtext("UitgevendeInstelling") or "").strip() in ONZE]
recent = [x for x in onze if d(x) >= GRENS]
print("datumbereik hele export:", min(d(x) for x in items), "tot", max(d(x) for x in items))
print("onze uitgevers sinds", GRENS, ":", dict(collections.Counter(x.findtext("UitgevendeInstelling") for x in recent)))
gevuld = [x for x in recent if (x.findtext("Wijzigingen") or "").strip()]
print("waarvan Wijzigingen gevuld:", len(gevuld), "van", len(recent))
print("alle veldnamen die voorkomen:", sorted({c.tag for x in items for c in x}))
for x in gevuld[:3]:
    print("\nvoorbeeld met gevulde velden:\n", ET.tostring(x, encoding="unicode")[:1500])
min_x = [x for x in recent if "-" in (x.findtext("Wijzigingen") or "")]
print("\nvoorbeelden met een minteken in Wijzigingen:", len(min_x))
for x in min_x[:2]:
    print(ET.tostring(x, encoding="unicode")[:1500])

print("\n=== Detailpagina's (NL)")
for x in sorted(recent, key=d, reverse=True)[:3] + ([min_x[0]] if min_x else []):
    i = x.findtext("meldingid")
    h = haal(DET + i).decode("utf-8", "replace")
    print(f"\n--- {d(x)} {x.findtext('UitgevendeInstelling')} id={i}")
    print("koppen:", [kaal(k) for k in re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>", h, re.S)][:15])
    for tabel in re.findall(r"<table.*?</table>", h, re.S)[:3]:
        print("   tabel:", [kaal(r)[:250] for r in re.findall(r"<tr[^>]*>(.*?)</tr>", tabel, re.S)][:3])
    if x is not None and i == sorted(recent, key=d, reverse=True)[0].findtext("meldingid"):
        m = re.search(r"utati.*?</table>", h, re.S)
        print("   ruwe HTML rond 'Mutaties':", (m.group(0) if m else "niet gevonden")[:2500])

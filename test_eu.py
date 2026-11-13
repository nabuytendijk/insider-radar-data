"""Proefrun 13: twee AFM-registers via de XML-export.
- MAR 19 (transacties leidinggevenden): buitenlandse uitgevers zoals Unilever Plc en Shell Plc
- Bestuurders en commissarissen (art. 5:48 Wft): Nederlandse NV's zoals Ahold, ASML, KPN, Adyen
Alleen lezen, schrijft niets weg."""
import re, html, time, collections, datetime as dt, urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (insider-radar proef)"}
EXP = "https://www.afm.nl/export.aspx?format=xml&type="
REG = {
    "MAR19": ("0ee836dc-5520-459d-bcf4-a4a689de6614",
              "https://www.afm.nl/nl-nl/sector/registers/meldingenregisters/transacties-leidinggevenden-mar19-/details?id="),
    "548": ("1b934036-12ad-4950-9773-31361d5adbd9",
            "https://www.afm.nl/nl-nl/sector/registers/meldingenregisters/bestuurders-commissarissen/details?id="),
}
ZOEK = ["semiconductor", "besi", "kpn", "ahold", "asml", "abn amro", "a.s.r", "asr nederland", "ing groep",
        "philips", "shell", "unilever", "wereldhave", "adyen", "asm international", "sif holding"]
GRENS = dt.date.today() - dt.timedelta(days=400)


def haal(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=180) as r:
        return r.read()


def kaal(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def datum(s):
    s = (s or "").strip()
    for f in ("%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def kies(tags, *stukjes):
    for t in tags:
        if any(s in t.lower() for s in stukjes):
            return t
    return None


voorbeelden = collections.defaultdict(list)
for naam, (typ, det) in REG.items():
    print(f"\n=== {naam}: XML-export")
    try:
        root = ET.fromstring(haal(EXP + typ))
    except Exception as e:
        print("export mislukt:", e); continue
    items = list(root)
    print("aantal vermeldingen:", len(items))
    eerste = items[0]
    print("velden van de eerste vermelding:")
    for c in eerste:
        print(f"   {c.tag} = {(c.text or '')[:80]!r}")
    tags = [c.tag for c in eerste]
    t_uitg = kies(tags, "uitgev", "instelling")
    t_dat = kies(tags, "datum", "date")
    t_id = kies(tags, "meldingid", "id")
    print("gekozen velden -> uitgever:", t_uitg, "| datum:", t_dat, "| id:", t_id)
    print("onleesbare datums (eerste 3):", [x.findtext(t_dat) for x in items if not datum(x.findtext(t_dat))][:3])
    totaal, recent = collections.Counter(), collections.Counter()
    for x in items:
        u = (x.findtext(t_uitg) or "").strip()
        low = u.lower()
        if any(k in low for k in ZOEK):
            totaal[u] += 1
            d = datum(x.findtext(t_dat))
            if d and d >= GRENS:
                recent[u] += 1
                voorbeelden[naam].append((d.isoformat(), u, x.findtext(t_id)))
    print(f"uitgevers die op een zoekwoord lijken (totaal | sinds {GRENS}):")
    for u, n in sorted(totaal.items()):
        print(f"   {u!r}: {n} | {recent.get(u, 0)}")

print("\n=== Detailpagina's 5:48 (opbouw en hoe een afname eruitziet)")
gezien = collections.Counter()
for d, u, i in sorted(voorbeelden["548"], reverse=True):
    if gezien[u] >= 3 or not i:
        continue
    gezien[u] += 1
    try:
        h = haal(REG["548"][1] + i).decode("utf-8", "replace")
    except Exception as e:
        print(d, u, i, "mislukt:", e); continue
    blokken = re.split(r"<h2[^>]*>", h)
    print(f"\n--- {d} {u} id={i}")
    for b in blokken[1:]:
        kop = kaal(b.split("</h2>")[0])
        if kop.lower().startswith(("positie", "mutatie", "position", "mutation")):
            rijen = re.findall(r"<tr[^>]*>(.*?)</tr>", b, re.S)
            print(f"   [{kop}]")
            for r in rijen[1:4]:
                print("      ", kaal(r)[:300])
    if sum(gezien.values()) == 1:
        m = re.search(r"<h2[^>]*>\s*Mutati.*?</table>", h, re.S)
        print("   ruwe HTML van het mutatieblok (eerste keer):", (m.group(0) if m else "niet gevonden")[:2500])
    time.sleep(0.5)
    if sum(gezien.values()) >= 12:
        break

print("\n=== Detailpagina MAR 19 (ter vergelijking, 1 stuk)")
for d, u, i in sorted(voorbeelden["MAR19"], reverse=True)[:1]:
    h = haal(REG["MAR19"][1] + i).decode("utf-8", "replace")
    print(d, u, i, "| bevat 'cc-mobile-title':", "cc-mobile-title" in h, "| 'Soort transactie':", "Soort transactie" in h)

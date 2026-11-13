#!/usr/bin/env python3
"""Haalt insidertransacties op uit de officiële Europese registers (alleen standaardbibliotheek).

Nederland: twee AFM-registers, elk via de volledige XML-export (een jaar historie) + detailpagina's:
           - Transacties leidinggevenden MAR 19 (o.a. BESI, Shell, Unilever, ASM, ASR, ING)
           - Bestuurders en commissarissen art. 5:48 Wft (o.a. Ahold, ASML, KPN, Philips, ABN Amro, Adyen)
Zweden:    Finansinspektionen (Volati; met paginering)
Schrijft naar data/transacties_eu.json in hetzelfde formaat als de Amerikaanse gegevens.
Gebruik:  python fetch_eu.py             haalt alles op
          python fetch_eu.py --selftest  test van de lezers, zonder internet
"""
import html, json, os, re, sys, time, datetime as dt
import urllib.request, urllib.error
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (insider-radar)"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
AFM = "https://www.afm.nl/nl-nl/sector/registers/meldingenregisters/transacties-leidinggevenden-mar19-"
AFM_BC = "https://www.afm.nl/nl-nl/sector/registers/meldingenregisters/bestuurders-commissarissen"
EXPORT = "https://www.afm.nl/export.aspx?format=xml&type="
EXPORT_MAR = "0ee836dc-5520-459d-bcf4-a4a689de6614"
EXPORT_BC = "1b934036-12ad-4950-9773-31361d5adbd9"
DAGEN_NL = 400           # hoe ver terug de AFM-registers worden gelezen
FI = "https://marknadssok.fi.se/Publiceringsklient/en-GB/Search/Search"
MAX_FI_PAGINAS = 8       # 10 rijen per pagina

# AFM: exacte naam van de uitgever zoals in de registers (kleine letters) -> (ticker, naam)
# Vastgesteld met proefrun 13 (13 nov 2026); beide registers gebruiken dezelfde schrijfwijze.
NL = {
    "be semiconductor industries n.v.": ("BESI", "BE Semiconductor"),
    "koninklijke kpn n.v.": ("KPN", "KPN"),
    "koninklijke ahold delhaize n.v.": ("AD", "Ahold Delhaize"),
    "asml holding n.v.": ("ASML", "ASML"),
    "abn amro bank nv": ("ABN", "ABN Amro"),
    "asr nederland n.v.": ("ASRNL", "ASR Nederland"),
    "ing groep n.v.": ("INGA", "ING"),
    "koninklijke philips n.v.": ("PHIA", "Philips"),
    "shell plc": ("SHELL", "Shell"),
    "sif holding n.v.": ("SIFG", "Sif Holding"),
    "unilever plc": ("UNA", "Unilever"),
    "wereldhave n.v.": ("WHA", "Wereldhave"),
    "adyen n.v.": ("ADYEN", "Adyen"),
    "asm international n.v.": ("ASM", "ASM International"),
}
# Zweden: zoekterm bij FI -> (ticker, naam, stukje van de uitgevernaam)
SE = [("Volati", "VOLO", "Volati", "volati")]
WEG = {"CIBUS"}          # niet meer gevolgd: bestaande regels worden opgeruimd
STATUS = {"WHA": "Positie", "CONSTI": "Positie"}


def haal(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < tries - 1:
                time.sleep(5 * (i + 1)); continue
            raise
        except Exception as e:  # verbinding verbroken, time-out, enz.
            if i < tries - 1:
                time.sleep(5 * (i + 1)); continue
            raise
    raise RuntimeError("niet gelukt: " + url)


def haal_bytes(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                return r.read()
        except Exception:
            if i < tries - 1:
                time.sleep(5 * (i + 1)); continue
            raise


def kaal(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def getal(s, nl=True):
    s = s.strip()
    s = s.replace(".", "").replace(",", ".") if nl else s.replace(",", "")
    return float(s)


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


# ---------- AFM ----------
def parse_afm_lijst(t):
    uit = []
    for tr in re.findall(r'<tr class="jq_registers_register-paged-list_results_tr">(.*?)</tr>', t, re.S):
        m = re.search(r"details\?id=([^\"&]+)", tr)
        cel = [kaal(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if m and len(cel) >= 3:
            uit.append({"id": m.group(1), "datum": m.group(1)[:8], "uitgever": cel[1], "persoon": cel[2]})
    return uit


def parse_afm_detail(t):
    tekst = kaal(t)
    m = re.search(r"Functie\s*:?\s*(.+?)\s*(?:Datum|Transacties|Meldingsplichtige|Uitgevende|Type instrument)", tekst)
    functie = m.group(1).strip() if m else ""
    regels = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        d = {kaal(a): kaal(b) for a, b in re.findall(r'<span class="cc-mobile-title">(.*?)</span>(.*?)</td>', tr, re.S)}
        if "Soort transactie" in d:
            regels.append(d)
    return functie, regels


def afm_rijen(lijstrij, ticker, naam, functie, regels):
    d = lijstrij["datum"]
    datum = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    uit = []
    for i, r in enumerate(regels):
        if r.get("Soort transactie") not in ("Koop", "Verkoop"):
            continue  # alleen echte aankopen en verkopen, geen toekenningen of optie-uitoefeningen
        if "aandeel" not in r.get("Type instrument", "").lower() and "certificaat" not in r.get("Type instrument", "").lower():
            continue
        try:
            koers, aantal = getal(r["Prijs"]), getal(r["Aantal"])
        except (KeyError, ValueError):
            continue
        if not aantal or not koers:
            continue
        opm = []
        if r.get("Aandelenoptie programma", "").lower() == "ja":
            opm.append("verband met aandelenoptieprogramma")
        if "OTC" in r.get("Plaats van handel", ""):
            opm.append("buiten de beurs (OTC)")
        uit.append({
            "id": f"{ticker}-{datum}-{lijstrij['id'][8:16]}-{i}", "ticker": ticker, "naam": naam,
            "status": STATUS.get(ticker, "Watchlist"), "datum": datum, "persoon": lijstrij["persoon"],
            "rol": functie or "Bestuur", "type": "koop" if r["Soort transactie"] == "Koop" else "verkoop",
            "aantal": int(round(aantal)), "koers": round(koers, 4), "valuta": r.get("Eenheid", "EUR") or "EUR",
            "bron": "AFM-register", "controle": "nee", "toelichting": "; ".join(opm),
        })
    return uit


def afm_export(typ):
    """Volledige XML-export van een AFM-register -> lijst van dicts per vermelding."""
    root = ET.fromstring(haal_bytes(EXPORT + typ))
    return [{c.tag: (c.text or "").strip() for c in x} for x in root]


def fetch_afm(bestaand, verwerkt):
    """MAR 19: alle meldingen van onze uitgevers uit het afgelopen jaar, via de XML-export."""
    grens = (dt.date.today() - dt.timedelta(days=DAGEN_NL)).strftime("%Y%m%d")
    lijst = []
    for v in afm_export(EXPORT_MAR):
        hit = NL.get(v.get("uitgevendeinstelling", "").lower())
        mid = v.get("meldingid", "")
        if hit and mid[:8] >= grens:
            lijst.append(({"id": mid, "datum": mid[:8], "uitgever": v["uitgevendeinstelling"],
                           "persoon": v.get("meldingsplichtige", "")}, hit))
    print(f"[afm] MAR 19: {len(lijst)} meldingen van jouw aandelen sinds {grens}")
    nieuw = bekeken = 0
    for r, hit in lijst:
        if r["id"] in verwerkt:
            continue
        bekeken += 1
        time.sleep(0.5)
        try:
            functie, regels = parse_afm_detail(haal(f"{AFM}/details?id={r['id']}"))
            for rij in afm_rijen(r, hit[0], hit[1], functie, regels):
                if rij["id"] not in bestaand and not dubbel(bestaand, rij):
                    bestaand[rij["id"]] = rij; nieuw += 1
            verwerkt.add(r["id"])
        except Exception as e:
            print(f"[afm] {r['uitgever']} {r['id']}: overgeslagen ({e})", file=sys.stderr)
    print(f"[afm] MAR 19: {bekeken} nieuwe meldingen bekeken, {nieuw} nieuwe aankopen/verkopen")


# ---------- AFM: bestuurders en commissarissen (art. 5:48 Wft) ----------
BC_RIJ = re.compile(r"Soort effect (?P<soort>.*?) Uitgevende instelling (?P<uitg>.*?) Aantal effecten (?P<aantal>[\d.,]+)"
                    r"(?: Valuta (?P<valuta>[A-Z]{3}))?(?: Waarde per aandeel (?P<waarde>[\d.,]+))?(?: Aantal stemmen)")


def parse_bc_detail(t):
    """Geeft {"Voorposities": [...], "Wijzigingen": [...], "Naposities": [...]}; ontbrekende blokken zijn leeg.
    Elke regel: dict met soort, aantal, valuta, waarde."""
    uit = {"Voorposities": [], "Wijzigingen": [], "Naposities": []}
    koppen = [(m.start(), kaal(m.group(1))) for m in re.finditer(r"<h[1-4][^>]*>(.*?)</h[1-4]>", t, re.S)]
    for n, (pos, kop) in enumerate(koppen):
        if kop not in uit:
            continue
        einde = koppen[n + 1][0] if n + 1 < len(koppen) else len(t)
        tabel = re.search(r"<table.*?</table>", t[pos:einde], re.S)
        if not tabel:
            continue
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tabel.group(0), re.S):
            m = BC_RIJ.search(kaal(tr))
            if m:
                uit[kop].append({"soort": m["soort"].strip(), "aantal": getal(m["aantal"]),
                                 "valuta": m["valuta"] or "EUR", "waarde": getal(m["waarde"]) if m["waarde"] else 0.0})
    return uit


def bc_rijen(melding, ticker, naam, blokken):
    """Alleen gewone aandelen met een waarde per aandeel. Het register vermeldt geen soort transactie:
    koop of verkoop volgt uit het verschil tussen de positie voor en na de melding."""
    gewoon = lambda r: "gewoon aandeel" in r["soort"].lower() or "certificaat" in r["soort"].lower()
    voor = sum(r["aantal"] for r in blokken["Voorposities"] if gewoon(r))
    na = sum(r["aantal"] for r in blokken["Naposities"] if gewoon(r))
    netto = na - voor
    wijz = [r for r in blokken["Wijzigingen"] if gewoon(r) and r["waarde"] > 0 and r["aantal"] > 0]
    if not wijz or netto == 0:
        return []
    ander = any(not gewoon(r) for r in blokken["Wijzigingen"])
    d = dt.datetime.strptime(melding["DatumMeldingsplicht"], "%m/%d/%Y").date().isoformat()
    opm = ["AFM 5:48: soort transactie niet vermeld, koop/verkoop afgeleid uit positie voor en na"]
    if ander:
        opm.append("in dezelfde melding ook toegekende of voorwaardelijke aandelen; mogelijk uitoefening of vesting")
    if abs(sum(r["aantal"] for r in wijz) - abs(netto)) > 0.5:
        opm.append(f"som van de wijzigingen wijkt af van het positieverschil ({netto:+,.0f})")
    uit = []
    for i, r in enumerate(wijz):
        uit.append({
            "id": f"{ticker}-{d}-bc{melding['meldingid']}-{i}", "ticker": ticker, "naam": naam,
            "status": STATUS.get(ticker, "Watchlist"), "datum": d, "persoon": melding.get("Meldingsplichtige", ""),
            "rol": "Bestuurder of commissaris", "type": "koop" if netto > 0 else "verkoop",
            "aantal": int(round(r["aantal"])), "koers": round(r["waarde"], 4), "valuta": r["valuta"],
            "bron": "AFM-register (5:48)", "controle": "ja" if ander or len(opm) > 2 else "nee",
            "toelichting": "; ".join(opm),
        })
    return uit


def fetch_afm_bc(bestaand, verwerkt):
    grens = dt.date.today() - dt.timedelta(days=DAGEN_NL)
    lijst = []
    for v in afm_export(EXPORT_BC):
        hit = NL.get(v.get("UitgevendeInstelling", "").lower())
        try:
            d = dt.datetime.strptime(v.get("DatumMeldingsplicht", ""), "%m/%d/%Y").date()
        except ValueError:
            continue
        if hit and d >= grens:
            lijst.append((v, hit))
    print(f"[afm-bc] 5:48: {len(lijst)} meldingen van jouw aandelen sinds {grens}")
    nieuw = bekeken = 0
    for v, hit in lijst:
        sleutel = "bc" + v["meldingid"]
        if sleutel in verwerkt:
            continue
        bekeken += 1
        time.sleep(0.5)
        try:
            for rij in bc_rijen(v, hit[0], hit[1], parse_bc_detail(haal(f"{AFM_BC}/details?id={v['meldingid']}"))):
                if rij["id"] not in bestaand and not dubbel(bestaand, rij):
                    bestaand[rij["id"]] = rij; nieuw += 1
            verwerkt.add(sleutel)
        except Exception as e:
            print(f"[afm-bc] {v.get('UitgevendeInstelling')} {v['meldingid']}: overgeslagen ({e})", file=sys.stderr)
    print(f"[afm-bc] 5:48: {bekeken} nieuwe meldingen bekeken, {nieuw} nieuwe aankopen/verkopen")


def dubbel(bestaand, rij):
    """Dezelfde transactie kan in beide AFM-registers staan: zelfde aandeel, datum, soort en aantal."""
    delen = [w.strip(",.").lower() for w in rij["persoon"].split() if len(w.strip(",.")) > 2]
    a = max(delen, key=len) if delen else ""  # achternaam: het langste woord, geen voorletters
    for r in bestaand.values():
        if (r["ticker"], r["datum"], r["type"], r["aantal"]) == (rij["ticker"], rij["datum"], rij["type"], rij["aantal"]) \
                and r.get("bron", "").startswith("AFM") and a and a in r.get("persoon", "").lower():
            return True
    return False


# ---------- Finansinspektionen ----------
def parse_fi(t):
    uit = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        c = [kaal(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(c) >= 15:
            uit.append(c)
    return uit


def fi_rij(c, ticker, naam):
    nat = c[5].lower()
    if nat not in ("acquisition", "disposal") or c[7].lower() != "share" or c[11].lower() != "quantity":
        return None
    try:
        aantal, koers = getal(c[10], nl=False), getal(c[12], nl=False)
        dd, mm, jj = c[9].split("/")
    except ValueError:
        return None
    datum = f"{jj}-{mm}-{dd}"
    opm = []
    if c[4].lower().startswith("y"):
        opm.append("gelieerde persoon")
    if c[14]:
        opm.append("status: " + c[14])
    return {
        "id": f"{ticker}-{datum}-fi-{c[2][:6].replace(' ', '')}-{int(aantal)}-{'k' if nat == 'acquisition' else 'v'}",
        "ticker": ticker, "naam": naam, "status": STATUS.get(ticker, "Watchlist"), "datum": datum,
        "persoon": c[2], "rol": c[3], "type": "koop" if nat == "acquisition" else "verkoop",
        "aantal": int(aantal), "koers": round(koers, 4), "valuta": c[13], "bron": "Finansinspektionen",
        "controle": "ja" if c[14] else "nee", "toelichting": "; ".join(opm),
    }


def fetch_fi(bestaand):
    grens = (dt.date.today() - dt.timedelta(days=400)).isoformat()
    for zoek, ticker, naam, stukje in SE:
        nieuw = gezien = 0
        try:
            for p in range(1, MAX_FI_PAGINAS + 1):
                url = f"{FI}?SearchFunctionType=Insyn&Utgivare={zoek}&button=search&paging=True&page={p}"
                rijen = parse_fi(haal(url))
                if not rijen:
                    break
                tel = 0
                for c in rijen:
                    if stukje not in c[1].lower():
                        continue
                    gezien += 1; tel += 1
                    r = fi_rij(c, ticker, naam)
                    if r and r["datum"] >= grens and r["id"] not in bestaand:
                        bestaand[r["id"]] = r; nieuw += 1
                if tel == 0:
                    break
                time.sleep(1)
        except Exception as e:
            print(f"[fi] {naam}: gestopt ({e})", file=sys.stderr)
        print(f"[fi] {naam}: {gezien} meldingen gezien, {nieuw} nieuwe aankopen/verkopen")


def markeer_afwijkingen(rijen, koersen):
    """Zet 'ter controle' bij transacties waarvan de koers meer dan 12% van de beurskoers afwijkt
    (bijvoorbeeld personeelsaandelen met korting, of een koers in een andere valuta)."""
    n = 0
    for r in rijen:
        serie = koersen.get(r["ticker"])
        if not serie:
            continue
        eerder = [p for d, p in serie if d <= r["datum"]]
        if not eerder or serie[0][0] > r["datum"]:
            continue
        markt = eerder[-1]
        if markt and abs(r["koers"] / markt - 1) > 0.12:
            r["controle"] = "ja"
            tekst = f"koers wijkt af van de beurskoers ({markt:g}); korting of andere valuta?"
            if tekst not in r.get("toelichting", ""):
                r["toelichting"] = (r.get("toelichting", "") + "; " if r.get("toelichting") else "") + tekst
            n += 1
    return n


def main():
    pad = os.path.join(OUT, "transacties_eu.json")
    bestaand = {r["id"]: r for r in load(pad, []) if r.get("ticker") not in WEG}
    vpad = os.path.join(OUT, "eu_verwerkt.json")
    verwerkt = set(load(vpad, []))
    for stap, f in (("afm", lambda: fetch_afm(bestaand, verwerkt)), ("afm-bc", lambda: fetch_afm_bc(bestaand, verwerkt)),
                    ("fi", lambda: fetch_fi(bestaand))):
        try:
            f()
        except Exception as e:
            print(f"[{stap}] mislukt: {e}", file=sys.stderr)
    koersen = load(os.path.join(OUT, "koersen.json"), {})
    n = markeer_afwijkingen(bestaand.values(), koersen)
    save(pad, sorted(bestaand.values(), key=lambda r: r["datum"], reverse=True))
    save(vpad, sorted(verwerkt))
    print(f"totaal in archief: {len(bestaand)} regels, {n} ter controle gemarkeerd")


def selftest():
    lijst = '''<tr class="jq_registers_register-paged-list_results_tr"> <td> <a href="/nl-nl/x/details?id=2026110536B2B2B2-9670-4417-8D87-1A85BD2EF00C" class="c"> 05 nov 2026</a> </td> <td> ASML Holding N.V. </td> <td> Test P. </td> </tr>'''
    l = parse_afm_lijst(lijst)
    assert l == [{"id": "2026110536B2B2B2-9670-4417-8D87-1A85BD2EF00C", "datum": "20261105", "uitgever": "ASML Holding N.V.", "persoon": "Test P."}], l
    det = '''<p>Functie: Chief Financial Officer Datum: 5 november 2026</p><table><thead><tr><th>Type instrument</th></tr></thead><tbody>
    <tr><td><span class="cc-mobile-title">Type instrument</span>Gewoon aandeel</td><td><span class="cc-mobile-title">Soort transactie</span>Verkoop</td><td><span class="cc-mobile-title">Aandelenoptie programma</span>Ja</td><td><span class="cc-mobile-title">Plaats van handel</span>EURONEXT</td><td><span class="cc-mobile-title">Prijs</span>1.825,50</td><td><span class="cc-mobile-title">Aantal</span>921,00</td><td><span class="cc-mobile-title">Eenheid</span>EUR</td></tr>
    <tr><td><span class="cc-mobile-title">Type instrument</span>Gewoon aandeel</td><td><span class="cc-mobile-title">Soort transactie</span>Omwisseling i.v.m. uitoefening</td><td><span class="cc-mobile-title">Prijs</span>3,60</td><td><span class="cc-mobile-title">Aantal</span>1,00</td></tr></tbody></table>'''
    f, regels = parse_afm_detail(det)
    r = afm_rijen(l[0], "ASML", "ASML", f, regels)
    assert f == "Chief Financial Officer" and len(r) == 1 and r[0]["type"] == "verkoop" and r[0]["koers"] == 1825.5 and r[0]["aantal"] == 921 and r[0]["datum"] == "2026-11-05", (f, r)
    c = ['07/11/2026', 'Volati AB', 'Anna Test', 'CEO', 'Yes', 'Acquisition', 'Volati', 'Share', 'SE0009143662', '06/11/2026', '1,339', 'Quantity', '22.85', 'SEK', '', 'Notification']
    x = fi_rij(c, "VOLO", "Volati")
    assert x["type"] == "koop" and x["aantal"] == 1339 and x["koers"] == 22.85 and x["datum"] == "2026-11-06" and x["toelichting"] == "gelieerde persoon", x
    assert fi_rij(c[:5] + ["Subscription"] + c[6:], "VOLO", "Volati") is None
    rr = [{"ticker": "X", "datum": "2026-02-03", "koers": 60.0, "toelichting": "", "controle": "nee"},
          {"ticker": "X", "datum": "2026-02-03", "koers": 74.0, "toelichting": "", "controle": "nee"}]
    n = markeer_afwijkingen(rr, {"X": [["2026-02-01", 75.0], ["2026-02-02", 75.5]]})
    assert n == 1 and rr[0]["controle"] == "ja" and rr[1]["controle"] == "nee", rr
    bc = """<h1>W. Test - Koninklijke KPN N.V. - Rotterdam</h1>
    <h2>Voorposities</h2><table><tr><th>Soort effect</th></tr>
    <tr><td><span class="cc-mobile-title">Soort effect</span>Gewoon aandeel</td><td><span class="cc-mobile-title">Uitgevende instelling</span>Koninklijke KPN N.V.</td><td><span class="cc-mobile-title">Aantal effecten</span>1.000,00</td><td><span class="cc-mobile-title">Aantal stemmen</span>1.000,00</td></tr></table>
    <h2>Wijzigingen</h2><table><tr><th>Soort effect</th></tr>
    <tr><td><span class="cc-mobile-title">Soort effect</span>Gewoon aandeel</td><td><span class="cc-mobile-title">Uitgevende instelling</span>Koninklijke KPN N.V.</td><td><span class="cc-mobile-title">Aantal effecten</span>400,00</td><td><span class="cc-mobile-title">Valuta</span>EUR</td><td><span class="cc-mobile-title">Waarde per aandeel</span>4,43</td><td><span class="cc-mobile-title">Aantal stemmen</span>400,00</td><td><span class="cc-mobile-title">Vrije hand beheer</span>Nee</td></tr></table>
    <h2>Naposities</h2><table><tr><th>Soort effect</th></tr>
    <tr><td><span class="cc-mobile-title">Soort effect</span>Gewoon aandeel</td><td><span class="cc-mobile-title">Uitgevende instelling</span>Koninklijke KPN N.V.</td><td><span class="cc-mobile-title">Aantal effecten</span>600,00</td><td><span class="cc-mobile-title">Aantal stemmen</span>600,00</td></tr></table>
    <h3>Er zijn fouten in uw formulier:</h3>"""
    b = parse_bc_detail(bc)
    m = {"meldingid": "999", "DatumMeldingsplicht": "10/31/2026", "Meldingsplichtige": "W. Test"}
    x = bc_rijen(m, "KPN", "KPN", b)
    assert len(x) == 1 and x[0]["type"] == "verkoop" and x[0]["aantal"] == 400 and x[0]["koers"] == 4.43 and x[0]["datum"] == "2026-10-31" and x[0]["controle"] == "nee", x
    award = bc.replace("Gewoon aandeel", "Performance award share").replace("4,43", "0,00")
    assert bc_rijen(m, "KPN", "KPN", parse_bc_detail(award)) == [], "toekenning zonder waarde moet wegvallen"
    zonder_voor = re.sub(r"<h2>Voorposities</h2>.*?</table>", "", bc, flags=re.S)
    y = bc_rijen(m, "KPN", "KPN", parse_bc_detail(zonder_voor))
    assert len(y) == 1 and y[0]["type"] == "koop", y
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest(); sys.exit(0)
    main()

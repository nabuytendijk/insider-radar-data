#!/usr/bin/env python3
"""Haalt insidertransacties op uit de officiële Europese registers (alleen standaardbibliotheek).

Nederland: AFM-register (de 50 nieuwste meldingen + detailpagina's)
Zweden:    Finansinspektionen (Volati, Cibus Nordic; met paginering)
Schrijft naar data/transacties_eu.json in hetzelfde formaat als de Amerikaanse gegevens.
Gebruik:  python fetch_eu.py             haalt alles op
          python fetch_eu.py --selftest  test van de lezers, zonder internet
"""
import html, json, os, re, sys, time, datetime as dt
import urllib.request, urllib.error

UA = {"User-Agent": "Mozilla/5.0 (insider-radar)"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
AFM = "https://www.afm.nl/nl-nl/sector/registers/meldingenregisters/transacties-leidinggevenden-mar19-"
FI = "https://marknadssok.fi.se/Publiceringsklient/en-GB/Search/Search"
MAX_FI_PAGINAS = 8       # 10 rijen per pagina

# AFM: stukje van de naam van de uitgever (kleine letters) -> (ticker, naam)
NL = [
    ("semiconductor", "BESI", "BE Semiconductor"), ("kpn", "KPN", "KPN"), ("ahold", "AD", "Ahold Delhaize"),
    ("asml", "ASML", "ASML"), ("abn amro", "ABN", "ABN Amro"), ("a.s.r.", "ASRNL", "ASR Nederland"),
    ("asr nederland", "ASRNL", "ASR Nederland"), ("ing groep", "INGA", "ING"), ("philips", "PHIA", "Philips"),
    ("shell", "SHELL", "Shell"), ("sif holding", "SIFG", "Sif Holding"), ("unilever", "UNA", "Unilever"),
    ("wereldhave", "WHA", "Wereldhave"), ("adyen", "ADYEN", "Adyen"),
]
# Zweden: zoekterm bij FI -> (ticker, naam, stukje van de uitgevernaam)
SE = [("Volati", "VOLO", "Volati", "volati"), ("Cibus", "CIBUS", "Cibus Nordic Real Estate", "cibus")]
STATUS = {"VOLO": "Positie", "BESI": "Positie", "CONSTI": "Positie"}


def haal(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < tries - 1:
                time.sleep(5 * (i + 1)); continue
            raise
    raise RuntimeError("niet gelukt: " + url)


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


def fetch_afm(bestaand, verwerkt):
    lijst = parse_afm_lijst(haal(AFM))
    print(f"[afm] {len(lijst)} meldingen op de lijst")
    nieuw = relevant = 0
    for r in lijst:
        low = r["uitgever"].lower()
        hit = next((x for x in NL if x[0] in low), None)
        if not hit or r["id"] in verwerkt:
            continue
        relevant += 1
        time.sleep(0.5)
        try:
            functie, regels = parse_afm_detail(haal(f"{AFM}/details?id={r['id']}"))
            for rij in afm_rijen(r, hit[1], hit[2], functie, regels):
                if rij["id"] not in bestaand:
                    bestaand[rij["id"]] = rij; nieuw += 1
            verwerkt.add(r["id"])
        except Exception as e:
            print(f"[afm] {r['uitgever']} {r['id']}: overgeslagen ({e})", file=sys.stderr)
    print(f"[afm] {relevant} meldingen van jouw aandelen bekeken, {nieuw} nieuwe aankopen/verkopen")


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
            time.sleep(0.5)
        print(f"[fi] {naam}: {gezien} meldingen gezien, {nieuw} nieuwe aankopen/verkopen")


def proef_afm_filters():
    """Eenmalig: kijkt of de AFM-lijst een datum- of zoekfilter via de webadresregel accepteert."""
    for q in ("?date-from=2026-01-01&date-till=2026-01-31", "?inputKeywords=semiconductor"):
        try:
            l = parse_afm_lijst(haal(AFM + q))
            print(f"[afm-proef] {q}: {len(l)} rijen, eerste: {l[0]['datum'] + ' ' + l[0]['uitgever'] if l else None}")
        except Exception as e:
            print(f"[afm-proef] {q}: mislukt ({e})")


def main():
    pad = os.path.join(OUT, "transacties_eu.json")
    bestaand = {r["id"]: r for r in load(pad, [])}
    vpad = os.path.join(OUT, "eu_verwerkt.json")
    verwerkt = set(load(vpad, []))
    for stap, f in (("afm", lambda: fetch_afm(bestaand, verwerkt)), ("fi", lambda: fetch_fi(bestaand))):
        try:
            f()
        except Exception as e:
            print(f"[{stap}] mislukt: {e}", file=sys.stderr)
    save(pad, sorted(bestaand.values(), key=lambda r: r["datum"], reverse=True))
    save(vpad, sorted(verwerkt))
    print(f"totaal in archief: {len(bestaand)} regels")
    if "--proef" in sys.argv:
        proef_afm_filters()


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
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest(); sys.exit(0)
    main()

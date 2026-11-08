#!/usr/bin/env python3
"""Insidertransacties uit Frankrijk (AMF) en Finland (Nasdaq Helsinki, Consti).
Schrijft naar data/transacties_eu2.json in hetzelfde formaat als de andere bestanden.
Gebruik:  python fetch_eu2.py            haalt alles op
          python fetch_eu2.py --selftest test van de lezers, zonder internet
"""
import html, io, json, os, re, subprocess, sys, time, datetime as dt
import urllib.parse
from fetch_eu import haal, getal, load, save, markeer_afwijkingen, STATUS, OUT, UA
import urllib.request

AMF = "https://bdif.amf-france.org/back/api/v1/"
NASDAQ = "https://api.news.eu.nasdaq.com/news/query.action"
MAX_AMF_PAGINAS = 60          # 100 meldingen per pagina (ca. 5 weken per 600)
DAGEN = 400

# AMF: (stukje van de naam in kleine letters, exact?) -> (ticker, naam)
FR = [
    ("danone", "BN", "Danone"), ("sanofi", "SAN", "Sanofi"), ("thales", "HO", "Thales"),
    ("totalenergies", "TTE", "TotalEnergies"), ("eutelsat", "ETL", "Eutelsat"),
    ("=ses", "SESG", "SES"), ("=ses s.a.", "SESG", "SES"),
]
MAANDEN = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
           "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12}
STATUS.setdefault("CONSTI", "Positie")


def get_bytes(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(4 * (i + 1))


def pdf_tekst(b):
    try:
        from pypdf import PdfReader
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pypdf"], check=False)
        from pypdf import PdfReader
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(b)).pages)


def num(s):
    s = re.sub(r"[\s\u202f\u00a0]", "", s)
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    return float(s)


def titel(s):
    return " ".join(w.capitalize() if w.isupper() else w for w in s.split())


# ---------- Frankrijk ----------
def parse_amf(t, ticker, naam, numero):
    """Leest de tekst van een AMF-melding. Geeft een rij of None (geen echte koop of verkoop van aandelen)."""
    def veld(label):
        m = re.search(label + r"\s*:\s*(.+)", t)
        return m.group(1).strip() if m else ""
    nat = veld("NATURE DE LA TRANSACTION").lower()
    if nat.startswith("acquisition") or nat.startswith("achat"):
        soort = "koop"
    elif nat.startswith("cession") or nat.startswith("vente"):
        soort = "verkoop"
    else:
        return None
    instr = veld(r"DESCRIPTION DE L.INSTRUMENT FINANCIER").lower()
    if not instr or ("action" not in instr and "share" not in instr) or any(x in instr for x in ("fcpe", "fie ", "fie-", "parts")):
        return None
    m = re.search(r"DATE DE LA TRANSACTION\s*:\s*(\d{1,2})\s+(\w+)\s+(\d{4})", t)
    if not m or m.group(2).lower() not in MAANDEN:
        return None
    datum = f"{m.group(3)}-{MAANDEN[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    agg = t.split("INFORMATIONS AGREGEES")[-1] if "INFORMATIONS AGREGEES" in t else t
    mp = re.search(r"PRIX\s*:\s*([\d\s\u202f\u00a0.,]+?)\s*([A-Za-z]+)", agg)
    mv = re.search(r"VOLUME\s*:\s*([\d\s\u202f\u00a0.,]+)", agg)
    if not mp or not mv:
        return None
    try:
        koers, aantal = num(mp.group(1)), num(mv.group(1))
    except ValueError:
        return None
    if not koers or not aantal:
        return None
    valuta = {"euro": "EUR", "euros": "EUR"}.get(mp.group(2).lower(), mp.group(2).upper())
    mn = re.search(r"PERSONNE ETROITEMENT LIEE\s*:\s*\n?\s*(.+)", t)
    pers, rol = "onbekend", "Bestuur"
    if mn:
        delen = mn.group(1).split(",", 1)
        pers = titel(delen[0].strip())
        rol = delen[1].strip() if len(delen) > 1 else rol
    opm = []
    if re.search(r"PROGRAMMES D.OPTIONS[^:]*:\s*OUI", t, re.I):
        opm.append("verband met aandelenoptieprogramma")
    return {
        "id": f"{ticker}-{datum}-amf-{numero[-8:]}-{'k' if soort == 'koop' else 'v'}", "ticker": ticker, "naam": naam,
        "status": STATUS.get(ticker, "Watchlist"), "datum": datum, "persoon": pers, "rol": rol, "type": soort,
        "aantal": int(round(aantal)), "koers": round(koers, 4), "valuta": valuta, "bron": "AMF (Frankrijk)",
        "controle": "nee", "toelichting": "; ".join(opm),
    }


def fr_match(raison):
    r = raison.lower().strip()
    for k, tk, nm in FR:
        if (k.startswith("=") and r == k[1:]) or (not k.startswith("=") and k in r):
            return tk, nm
    return None


def fetch_amf(bestaand, verwerkt):
    grens = (dt.date.today() - dt.timedelta(days=DAGEN)).isoformat()
    gezien = nieuw = 0
    for p in range(MAX_AMF_PAGINAS):
        j = json.loads(haal(AMF + f"informations?TypesInformation=DD&From={p * 100}&Size=100"))
        res = j.get("result") or []
        if not res:
            break
        for it in res:
            d = (it.get("dateInformation") or it.get("datePublication") or "")[:10]
            if d and d < grens:
                res = None; break
            hit = None
            for so in it.get("societes") or []:
                hit = hit or fr_match(so.get("raisonSociale") or "")
            if not hit or it["numero"] in verwerkt or not it.get("documents"):
                continue
            gezien += 1
            try:
                b = get_bytes(AMF + "documents/" + urllib.parse.quote(it["documents"][0]["path"], safe="/"))
                r = parse_amf(pdf_tekst(b), hit[0], hit[1], it["numero"])
                if r and r["id"] not in bestaand:
                    bestaand[r["id"]] = r; nieuw += 1
                verwerkt.add(it["numero"])
            except Exception as e:
                print(f"[amf] {hit[1]} {it['numero']}: overgeslagen ({e})", file=sys.stderr)
            time.sleep(0.3)
        if res is None:
            break
        time.sleep(0.3)
    print(f"[amf] {gezien} meldingen gelezen, {nieuw} nieuwe aankopen/verkopen")


# ---------- Finland (Consti) ----------
def parse_nasdaq(t, ticker, naam):
    """Leest de tekst van een 'Managers' Transactions'-bericht. Geeft een lijst rijen."""
    t = re.sub(r"\s+", " ", t)
    mp = re.search(r"Name:\s*(.+?)\s+Position:\s*(.+?)\s+Issuer:", t)
    pers, rol = (mp.group(1).strip(), mp.group(2).strip()) if mp else ("onbekend", "Bestuur")
    uit = []
    for blok in re.split(r"(?=Transaction date:)", t)[1:]:
        mdat = re.match(r"Transaction date:\s*(\d{4}-\d{2}-\d{2})", blok)
        mnat = re.search(r"Nature of transaction:\s*([A-Za-z]+)", blok)
        if not mdat or not mnat or "Instrument type: SHARE" not in blok:
            continue
        nat = mnat.group(1).upper()
        if nat not in ("ACQUISITION", "DISPOSAL"):
            continue
        mv = re.search(r"Aggregated transactions[^:]*:\s*Volume:\s*([\d.,\s]+?)\s+Volume weighted average price:\s*([\d.,]+)\s*([A-Z]{3})", blok)
        if not mv:
            continue
        aantal, koers = num(mv.group(1)), num(mv.group(2))
        opm = ["verband met aandelenoptieprogramma"] if "Linked to stock option programme" in blok else []
        uit.append({
            "id": f"{ticker}-{mdat.group(1)}-nq-{re.sub('[^A-Za-z]', '', pers)[:6]}-{int(aantal)}-{'k' if nat == 'ACQUISITION' else 'v'}",
            "ticker": ticker, "naam": naam, "status": STATUS.get(ticker, "Watchlist"), "datum": mdat.group(1),
            "persoon": pers, "rol": rol, "type": "koop" if nat == "ACQUISITION" else "verkoop",
            "aantal": int(round(aantal)), "koers": round(koers, 4), "valuta": mv.group(3),
            "bron": "Nasdaq Helsinki", "controle": "nee", "toelichting": "; ".join(opm),
        })
    return uit


def fetch_consti(bestaand, verwerkt):
    grens = (dt.date.today() - dt.timedelta(days=DAGEN)).isoformat()
    gezien = nieuw = 0
    basis = ("countResults=true&globalGroup=exchangeNotice&displayLanguage=en&timeZone=CET"
             "&dateMask=yyyy-MM-dd+HH%3Amm%3Ass&limit=50&dir=DESC&globalName=NordicAllMarkets&callback=cb"
             "&freeText=Consti+Managers")
    for p in range(6):
        r = haal(f"{NASDAQ}?{basis}&start={p * 50}")
        items = json.loads(r[r.index("(") + 1:r.rindex(")")])["results"]["item"]
        if not items:
            break
        for it in items:
            if "Managers" not in it.get("cnsCategory", "") or "consti" not in it.get("headline", "").lower():
                continue
            if it["releaseTime"][:10] < grens:
                return print(f"[consti] {gezien} meldingen gelezen, {nieuw} nieuwe aankopen/verkopen")
            sleutel = "nq" + str(it["disclosureId"])
            if sleutel in verwerkt:
                continue
            gezien += 1
            try:
                v = haal(it["messageUrl"])
                t = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<(script|style).*?</\1>|<[^>]+>", " ", v)))
                for rij in parse_nasdaq(t, "CONSTI", "Consti"):
                    if rij["id"] not in bestaand:
                        bestaand[rij["id"]] = rij; nieuw += 1
                verwerkt.add(sleutel)
            except Exception as e:
                print(f"[consti] {it['headline']}: overgeslagen ({e})", file=sys.stderr)
            time.sleep(0.3)
    print(f"[consti] {gezien} meldingen gelezen, {nieuw} nieuwe aankopen/verkopen")


def main():
    pad = os.path.join(OUT, "transacties_eu2.json")
    bestaand = {r["id"]: r for r in load(pad, [])}
    vpad = os.path.join(OUT, "eu2_verwerkt.json")
    verwerkt = set(load(vpad, []))
    for stap, f in (("amf", lambda: fetch_amf(bestaand, verwerkt)), ("consti", lambda: fetch_consti(bestaand, verwerkt))):
        try:
            f()
        except Exception as e:
            print(f"[{stap}] mislukt: {e}", file=sys.stderr)
    n = markeer_afwijkingen(bestaand.values(), load(os.path.join(OUT, "koersen.json"), {}))
    save(pad, sorted(bestaand.values(), key=lambda r: r["datum"], reverse=True))
    save(vpad, sorted(verwerkt))
    print(f"totaal in archief: {len(bestaand)} regels, {n} ter controle gemarkeerd")


def selftest():
    t = """2026DD1149162
FR0000120271 - DD194708
NOM /FONCTION DE LA PERSONNE EXERCANT DES RESPONSABILITES DIRIGEANTES OU DE LA
PERSONNE ETROITEMENT LIEE :
NAMITA SHAH, Membre du Comité exécutif
DETAIL DE LA TRANSACTION
DATE DE LA TRANSACTION : 05 novembre 2026
NATURE DE LA TRANSACTION : Cession
DESCRIPTION DE L’INSTRUMENT FINANCIER : ACTIONS TOTALENERGIES
INFORMATION DETAILLEE PAR OPERATION
PRIX UNITAIRE : 82.7047 Euro
VOLUME : 11 781
INFORMATIONS AGREGEES
PRIX : 82.7047 Euro
VOLUME : 11 781
TRANSACTION LIEE A L’EXERCICE DE PROGRAMMES D’OPTIONS SUR ACTIONS : NON"""
    r = parse_amf(t, "TTE", "TotalEnergies", "2026DD1149162")
    assert r and r["type"] == "verkoop" and r["aantal"] == 11781 and r["koers"] == 82.7047 and r["datum"] == "2026-11-05" \
        and r["persoon"] == "Namita Shah" and r["rol"].startswith("Membre"), r
    assert parse_amf(t.replace("ACTIONS TOTALENERGIES", "FIE - TOTALENERGIES ACTIONNARIAT"), "TTE", "T", "x") is None
    n = ("Name: Risto Kivi Position: Other senior manager Issuer: Consti Oyj Notification type: INITIAL NOTIFICATION "
         "Transaction date: 2024-06-18 Outside a trading venue Instrument type: SHARE ISIN: FI4000178256 "
         "Nature of transaction: ACQUISITION Transaction details (1): Volume: 11500 Unit price: 4.8 EUR "
         "Aggregated transactions (1): Volume: 11500 Volume weighted average price: 4.8 EUR CONSTI PLC")
    x = parse_nasdaq(n, "CONSTI", "Consti")
    assert len(x) == 1 and x[0]["persoon"] == "Risto Kivi" and x[0]["aantal"] == 11500 and x[0]["koers"] == 4.8 and x[0]["type"] == "koop", x
    assert fr_match("SES") == ("SESG", "SES") and fr_match("Sesame") is None and fr_match("DANONE SA")[0] == "BN"
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()

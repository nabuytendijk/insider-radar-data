"""Proefrun 7: BaFin detail/export, AMF-lijst + PDF-tekst."""
import json, re, subprocess, sys, urllib.request, urllib.parse, html

UA = {"User-Agent": "Mozilla/5.0 (insider-radar proef)", "Accept": "*/*"}


def get(url, data=None, headers=None, raw=False):
    h = dict(UA)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=40) as r:
        b = r.read()
        return r.status, (b if raw else b.decode("utf-8", "replace"))


def kop(t):
    print("\n" + "=" * 70 + "\n" + t + "\n" + "=" * 70)


def tekst(h):
    h = re.sub(r"(?s)<(script|style).*?</\1>", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(h)).strip()


# ---------- BaFin ----------
kop("BaFin: detailpagina meldungId=34605")
B = "https://portal.mvp.bafin.de/database/DealingsInfo/"
try:
    form = {"emittentIsin": "DE0008430026", "emittentName": "", "meldepflichtigerName": "",
            "zeitraum": "0", "zeitraumVon": "", "zeitraumBis": "", "emittentButton": "Suche Emittent"}
    ck = urllib.request.HTTPCookieProcessor()
    op = urllib.request.build_opener(ck)
    op.addheaders = list(UA.items())
    r = op.open(B + "sucheForm.do", urllib.parse.urlencode(form).encode(), timeout=40).read().decode("utf-8", "replace")
    for l in re.findall(r'(?i)href="([^"]*(?:csv|xml|export)[^"]*)"', r):
        print("EXPORT", html.unescape(l))
    d = op.open(B + "ergebnisListe.do?cmd=loadMeldepflichtigeAction&emittentBafinId=40001467&meldungId=34605", timeout=40).read().decode("utf-8", "replace")
    print("DETAIL", tekst(d)[300:2500])
except Exception as e:
    print("FOUT", e)

# ---------- AMF ----------
kop("AMF: lijst DD + bedrijven")
A = "https://bdif.amf-france.org/back/api/v1/"
items = []
try:
    for frm in range(0, 600, 100):
        s, b = get(A + "informations?TypesInformation=DD&From=%d&Size=100" % frm)
        items += json.loads(b)["result"]
    print("opgehaald:", len(items), "van", items[-1].get("dateInformation"), "tot", items[0].get("dateInformation"))
    it = items[0]
    print("SOCIETES", json.dumps(it.get("societes"), ensure_ascii=False)[:600])
    print("DATA-keys", [k for k in it.keys()])
    namen = {}
    for it in items:
        for so in it.get("societes") or []:
            namen[so.get("raisonSociale")] = namen.get(so.get("raisonSociale"), 0) + 1
    zoek = ["danone", "sanofi", "thales", "totalenergies", "ses", "eutelsat", "bnp", "axa"]
    for n, c in sorted(namen.items(), key=lambda x: -x[1]):
        if n and any(z in n.lower() for z in zoek):
            print("BEDRIJF", n, c)
except Exception as e:
    print("FOUT", e)

kop("AMF: PDF van een melding")
try:
    pad = None
    for it in items:
        for so in it.get("societes") or []:
            if so.get("raisonSociale") and re.search("danone|sanofi|totalenergies|thales", so["raisonSociale"], re.I):
                pad = it["documents"][0]["path"]; print("gekozen:", so["raisonSociale"], pad); break
        if pad: break
    pad = pad or items[0]["documents"][0]["path"]
    for u in [A + "documents/" + pad, A + "documents?path=" + urllib.parse.quote(pad),
              "https://bdif.amf-france.org/back/api/v1/documents/" + urllib.parse.quote(pad, safe="/")]:
        try:
            s, b = get(u, raw=True)
            print(u[:90], s, len(b), b[:8])
            if b[:4] == b"%PDF":
                subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pypdf"], check=False)
                import io
                from pypdf import PdfReader
                t = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(b)).pages)
                print("PDFTEKST", t[:2500])
                break
        except Exception as e:
            print(u[:90], "FOUT", e)
except Exception as e:
    print("FOUT", e)

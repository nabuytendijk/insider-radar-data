"""Proefrun 12: AFM-register MAR 19. Wat staat er in de export, en welke filters accepteert de lijst?"""
import csv, io, re, collections, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (insider-radar proef)"}
AFM = "https://www.afm.nl/nl-nl/sector/registers/meldingenregisters/transacties-leidinggevenden-mar19-"
EXP = "https://www.afm.nl/export.aspx?type=0ee836dc-5520-459d-bcf4-a4a689de6614&format="
NAMEN = ["semiconductor", "kpn", "ahold", "asml", "abn amro", "a.s.r", "asr nederland", "ing groep",
         "philips", "shell", "unilever", "wereldhave", "adyen", "asm international"]


def haal(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=180) as r:
        return r.read(), r.headers.get("Content-Type")


def tekst(b):
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return b.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", "replace"), "utf-8 (vervangen)"


print("=== 1. CSV-export")
try:
    b, ct = haal(EXP + "csv")
    t, enc = tekst(b)
    regels = t.splitlines()
    print("bytes:", len(b), "| type:", ct, "| codering:", enc, "| regels:", len(regels))
    sep = ";" if regels[0].count(";") > regels[0].count(",") else ","
    rows = list(csv.reader(io.StringIO(t), delimiter=sep))
    print("scheidingsteken:", repr(sep))
    print("kolommen:", rows[0])
    for r in rows[1:4]:
        print("eerste rij:", r)
    for r in rows[-2:]:
        print("laatste rij:", r)
    tel = collections.Counter()
    for r in rows[1:]:
        regel = " ".join(r).lower()
        for n in NAMEN:
            if n in regel:
                tel[n] += 1
    print("treffers per uitgever:", dict(tel))
    for n in ("ahold", "asml", "wereldhave", "philips"):
        for h in [r for r in rows[1:] if n in " ".join(r).lower()][:3]:
            print(f"voorbeeld {n}:", h)
except Exception as e:
    print("CSV mislukt:", e)

print("=== 2. XML-export (begin)")
try:
    b, ct = haal(EXP + "xml")
    t, enc = tekst(b)
    print("bytes:", len(b), "| type:", ct)
    print(t[:2500])
except Exception as e:
    print("XML mislukt:", e)

print("=== 3. Lijstpagina: formuliervelden en paginering")
try:
    h, _ = haal(AFM)
    h = h.decode("utf-8", "replace")
    print("invoervelden:", sorted(set(re.findall(r'<input[^>]+name="([^"]+)"', h))))
    print("pagineringsaanwijzingen:", sorted(set(re.findall(r'(data-[a-z-]*page[a-z-]*="[^"]*"|[?&](?:page|p|pageNumber|pagina|pageIndex)=\d+)', h)))[:30])
    print("formulieren:", re.findall(r'<form[^>]*>', h)[:5])
except Exception as e:
    print("lijstpagina mislukt:", e)

print("=== 4. Zoekfilter op de lijst")
RIJ = r'<tr class="jq_registers_register-paged-list_results_tr">(.*?)</tr>'
for q in ("?KeyWords=ahold", "?KeyWords=asml", "?KeyWords=wereldhave", "?KeyWords=ahold&page=2"):
    try:
        h, _ = haal(AFM + q)
        h = h.decode("utf-8", "replace")
        rijen = re.findall(RIJ, h, re.S)
        ids = [re.search(r"details\?id=([^\"&]+)", r).group(1) for r in rijen if re.search(r"details\?id=", r)]
        uitg = collections.Counter(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)[1])).strip()
                                   for r in rijen if len(re.findall(r"<td", r)) >= 3)
        tot = re.search(r"<strong>\s*([\d.]+)\s*</strong>\s*Resultaten", h) or re.search(r"([\d.]+)\s*</[^>]+>\s*Resultaten", h)
        print(f"{q}: {len(rijen)} rijen, totaal volgens pagina: {tot.group(1) if tot else '?'}, "
              f"van {ids[-1][:8] if ids else '-'} tot {ids[0][:8] if ids else '-'}, uitgevers: {dict(uitg)}")
    except Exception as e:
        print(f"{q}: mislukt ({e})")

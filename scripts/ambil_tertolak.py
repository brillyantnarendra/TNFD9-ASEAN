import csv
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ekstrak
from ekstrak_paragraf import IDIOM, P_PING

BENIH = 20261110
TERTOLAK = []
_asli = ekstrak.lolos_saringan


def _catat(teks):
    ok, n_inti = _asli(teks)
    if not ok:
        bersih = teks
        for p in IDIOM:
            bersih = p.sub(" ", bersih)
        n_ping = sum(1 for p in P_PING if p.search(bersih))
        TERTOLAK.append({"teks": teks, "n_ping": n_ping})
    return ok, n_inti


ekstrak.lolos_saringan = _catat


def main():
    if len(sys.argv) not in (2, 4):
        print("Argumen tidak lengkap.")
        return
    n1, n2 = (75, 75) if len(sys.argv) == 2 else (int(sys.argv[2]), int(sys.argv[3]))
    pdfs = sorted(p for p in Path(sys.argv[1]).glob("*.pdf")
                  if re.fullmatch(r"[A-Z]+_[A-Z0-9]+_\d{4}", p.stem))
    print("PDF: %d" % len(pdfs))
    semua = []
    t0 = time.time()
    for i, p in enumerate(pdfs, 1):
        neg, bank, thn = (p.stem.split("_") + ["", "", ""])[:3]
        TERTOLAK.clear()
        try:
            hasil = ekstrak.satu_pdf(p)
        except Exception as e:
            print("  %3d %-40s GAGAL %s" % (i, p.name[:40], type(e).__name__))
            continue
        terlihat = set()
        for t in TERTOLAK:
            k = re.sub(r"\W+", "", t["teks"].lower())[:160]
            if k in terlihat:
                continue
            terlihat.add(k)
            semua.append({"negara": neg, "bank": bank, "tahun": thn,
                          "kata": len(t["teks"].split()), "n_ping": t["n_ping"],
                          "teks": t["teks"]})
        print("  %3d/%d %-40s lolos %4d | ditolak %5d   %.0f dtk"
              % (i, len(pdfs), p.name[:40], len(hasil), len(terlihat), time.time() - t0))

    for j, b in enumerate(semua, 1):
        b["id_tolak"] = j
        b["strata"] = "one_peripheral_term" if b["n_ping"] == 1 else "no_term"
    s1 = [b for b in semua if b["strata"] == "one_peripheral_term"]
    s2 = [b for b in semua if b["strata"] == "no_term"]
    rng = random.Random(BENIH)
    pil = rng.sample(s1, min(n1, len(s1))) + rng.sample(s2, min(n2, len(s2)))
    rng.shuffle(pil)

    with open("Tertolak_semua.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id_tolak", "negara", "bank", "tahun", "kata", "n_ping", "strata", "teks"])
        w.writeheader()
        w.writerows(semua)
    with open("Kunci_Tertolak.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["no", "id_tolak", "strata"])
        for no, b in enumerate(pil, 1):
            w.writerow([no, b["id_tolak"], b["strata"]])
    with open("ringkasan_tertolak.txt", "w", encoding="utf-8") as f:
        f.write("Unit ditolak (unik per bank-tahun): %d\n" % len(semua))
        f.write("one_peripheral_term  (1 istilah pinggiran): %d, sampel %d\n" % (len(s1), min(n1, len(s1))))
        f.write("no_term (0 istilah pinggiran): %d, sampel %d\n" % (len(s2), min(n2, len(s2))))
        f.write("Benih acak: %d\n" % BENIH)

    import openpyxl
    from openpyxl.styles import Alignment, Font
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kode"
    ws.append(["no", "negara", "bank", "tahun", "teks", "kode",
               "catatan (opsional)"])
    for no, b in enumerate(pil, 1):
        ws.append([no, b["negara"], b["bank"], b["tahun"], b["teks"], "", ""])
    pilihan = '"A1,A2,A3,A4,B1,B2,B3,B4,B5,bukan alam,bukan alam iklim,rusak"'
    dv = DataValidation(type="list", formula1=pilihan, allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("F2:F%d" % (len(pil) + 1))
    ws.column_dimensions["E"].width = 110
    ws.column_dimensions["F"].width = 18
    ws.column_dimensions["G"].width = 30
    for row in ws.iter_rows(min_row=2):
        row[4].alignment = Alignment(wrap_text=True, vertical="top")
    for c in ws[1]:
        c.font = Font(bold=True)
    ws.freeze_panes = "A2"
    wb.save("Lembar_Tertolak.xlsx")

    print("\nDitolak: %d unit (one_peripheral_term %d, no_term %d)" % (len(semua), len(s1), len(s2)))
    print("Ditulis: Lembar_Tertolak.xlsx (%d unit), Kunci_Tertolak.csv, Tertolak_semua.csv, ringkasan_tertolak.txt"
          % len(pil))


if __name__ == "__main__":
    main()

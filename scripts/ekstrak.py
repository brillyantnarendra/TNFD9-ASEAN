import csv
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import pymupdf4llm
except ImportError:
    print("pymupdf4llm belum terpasang.  pip install pymupdf4llm"); sys.exit(1)
try:
    import openpyxl
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.styles import Alignment, Font, PatternFill
except ImportError:
    print("openpyxl belum terpasang.  pip install openpyxl"); sys.exit(1)

from ekstrak_paragraf import lolos_saringan, pecah_panjang, rapikan, MIN_KATA

MIN_KATA_BLOK = 8
MAKS_KATA_TABEL = 150
AMBANG_HEADER = 0.30

AWAL_GBR = "<!-- Start of picture text -->"
AKHIR_GBR = "<!-- End of picture text -->"
JUDUL = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")


def pecah_tabel(mentah, maks=MAKS_KATA_TABEL):
    baris = [b for b in mentah.split("\n") if b.strip()]
    if len(baris) < 2:
        return [mentah]
    kepala = [baris[0]]
    mulai = 1
    if len(baris) > 1 and set(baris[1].replace("|", "").strip()) <= set("-: "):
        kepala.append(baris[1])
        mulai = 2
    n_kepala = len(" ".join(kepala).split())
    isi = baris[mulai:]
    if not isi:
        return [mentah]

    potongan, kini, n = [], [], n_kepala
    for b in isi:
        k = len(b.split())
        if kini and n + k > maks:
            potongan.append("\n".join(kepala + kini))
            kini, n = [], n_kepala
        kini.append(b)
        n += k
    if kini:
        potongan.append("\n".join(kepala + kini))
    return potongan


def bersihkan_markdown(t):
    t = t.replace("<br>", " ")
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[*_`]{1,3}", "", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t)
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.M)
    return rapikan(t)


def blok_halaman(md):
    keluar = []
    judul = ""
    baris = md.split("\n")
    i = 0
    while i < len(baris):
        b = baris[i]

        if AWAL_GBR in b:
            kumpul = [b.replace(AWAL_GBR, "")]
            while i + 1 < len(baris) and AKHIR_GBR not in baris[i]:
                i += 1
                kumpul.append(baris[i])
            teks = "\n".join(kumpul).replace(AKHIR_GBR, "")
            keluar.append(("gambar", judul, teks))
            i += 1
            continue

        if b.lstrip().startswith("|"):
            kumpul = []
            while i < len(baris) and baris[i].lstrip().startswith("|"):
                kumpul.append(baris[i])
                i += 1
            keluar.append(("tabel", judul, "\n".join(kumpul)))
            continue

        m = JUDUL.match(b)
        if m:
            judul = bersihkan_markdown(m.group(1))[:120]
            i += 1
            continue

        if b.strip():
            kumpul = []
            while (i < len(baris) and baris[i].strip()
                   and not baris[i].lstrip().startswith("|")
                   and AWAL_GBR not in baris[i]
                   and not JUDUL.match(baris[i])):
                kumpul.append(baris[i])
                i += 1
            keluar.append(("prosa", judul, " ".join(kumpul)))
            continue
        i += 1
    return keluar


def baris_sering(halaman_md, ambang=AMBANG_HEADER):
    from collections import Counter
    hit = Counter()
    for md in halaman_md:
        for b in {x.strip() for x in md.split("\n") if x.strip()}:
            if len(b) <= 90:
                hit[b] += 1
    batas = max(3, int(len(halaman_md) * ambang))
    return {b for b, n in hit.items() if n >= batas}


def satu_pdf(path):
    md = pymupdf4llm.to_markdown(str(path), page_chunks=True,
                                 show_progress=False, graphics_limit=6000)
    halaman = []
    for bag in md:
        halaman.append(bag.get("text", "") if isinstance(bag, dict) else str(bag))

    buang = baris_sering(halaman)
    hasil = []
    for n, teks_md in enumerate(halaman, start=1):
        if not teks_md.strip():
            continue
        bersih = "\n".join(b for b in teks_md.split("\n") if b.strip() not in buang)
        for jenis, judul, mentah in blok_halaman(bersih):
            if jenis == "tabel":
                potong = [rapikan(x.replace("|", " | ")) for x in pecah_tabel(mentah)]
            elif jenis == "prosa":
                t = bersihkan_markdown(mentah)
                potong = pecah_panjang(t) if t else []
            else:
                t = bersihkan_markdown(mentah)
                potong = [t] if t else []
            n_potong = len(potong)
            for ke, q in enumerate(potong, start=1):
                if not q:
                    continue
                n_kata = len(q.split())
                batas = MIN_KATA if jenis == "prosa" else MIN_KATA_BLOK
                if n_kata < batas:
                    continue
                ok, n_inti = lolos_saringan(q)
                if not ok:
                    continue
                hasil.append(dict(hal=n, jenis=jenis, judul=judul,
                                  bagian=("%d/%d" % (ke, n_potong)
                                          if jenis == "tabel" and n_potong > 1 else ""),
                                  kata=n_kata, inti=n_inti, teks=q))
    return hasil


def tulis_lembar(baris, tujuan):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pengodean"
    kolom = ["id", "negara", "bank", "tahun", "hal", "jenis", "bagian", "kata",
             "inti", "teks_paragraf", "kode", "kalimat_bukti", "catatan"]
    ws.append(kolom)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DCE6F1")
    for b in baris:
        ws.append([b["id"], b["negara"], b["bank"], b["tahun"], b["hal"],
                   b["jenis"], b.get("bagian", ""), b["kata"], b["inti"],
                   b["teks"], "", "", ""])
    lebar = dict(A=7, B=11, C=14, D=8, E=7, F=9, G=7, H=7, I=7, J=95, K=9,
                 L=55, M=26)
    for k, v in lebar.items():
        ws.column_dimensions[k].width = v
    for r in range(2, ws.max_row + 1):
        ws.cell(r, 10).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(r, 11).alignment = Alignment(wrap_text=True, vertical="top")
    if ws.max_row >= 2:
        dv = DataValidation(type="list", allow_blank=True, formula1=
            '"A1,A2,A3,A4,B1,B2,B3,B4,B5"')
        ws.add_data_validation(dv)
        dv.add("K2:K%d" % ws.max_row)
    ws.freeze_panes = "A2"

    ket = wb.create_sheet("Kode")
    ket.append(["jenis blok", "artinya"])
    for a, b in [("prosa", "paragraf naratif biasa"),
                 ("tabel", "satu tabel utuh; bacalah kepala kolomnya lebih dahulu"),
                 ("gambar", "teks di dalam infografis atau diagram; urutannya "
                            "mungkin melintang, jadi baca sebagai daftar, bukan kalimat"),
                 ("bagian", "potongan ke berapa dari satu tabel panjang, misalnya 2/5. "
                            "Kepala kolom diulang di setiap potongan.")]:
        ket.append([a, b])
    wb.save(tujuan)


def utama(folder):
    folder = Path(folder)
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        print("Tidak ada PDF di", folder.resolve()); sys.exit(1)
    print("Berkas: %d\n" % len(pdfs))

    baris, gagal, nomor = [], [], 0
    t0 = time.time()
    for n, p in enumerate(pdfs, 1):
        bag = p.stem.split("_")
        neg, bank, thn = (bag + ["", "", ""])[:3]
        t1 = time.time()
        try:
            hasil = satu_pdf(p)
        except Exception as e:
            gagal.append("%s (%s)" % (p.name, type(e).__name__))
            print("  %3d/%3d  %-40s GAGAL %s" % (n, len(pdfs), p.name[:40],
                                                 type(e).__name__))
            continue
        unik, terlihat = [], set()
        for h in hasil:
            k = re.sub(r"\W+", "", h["teks"].lower())[:160]
            if k in terlihat:
                continue
            terlihat.add(k)
            unik.append(h)
        for h in unik:
            nomor += 1
            h.update(id=nomor, negara=neg, bank=bank, tahun=thn)
            baris.append(h)
        jns = {}
        for h in unik:
            jns[h["jenis"]] = jns.get(h["jenis"], 0) + 1
        print("  %3d/%3d  %-40s %4d par  (prosa %d, tabel %d, gambar %d)  %.0f dtk"
              % (n, len(pdfs), p.name[:40], len(unik), jns.get("prosa", 0),
                 jns.get("tabel", 0), jns.get("gambar", 0), time.time() - t1))

    if not baris:
        print("\nTidak ada paragraf kandidat sama sekali."); sys.exit(1)

    with open("paragraf.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "negara", "bank", "tahun", "hal",
                                          "jenis", "bagian", "judul", "kata",
                                          "inti", "teks"])
        w.writeheader()
        for b in baris:
            w.writerow({k: b[k] for k in w.fieldnames})
    tulis_lembar(baris, "Lembar_Pengodean.xlsx")

    print("\n" + "=" * 60)
    print("TOTAL %d paragraf kandidat dari %d berkas  (%.0f dtk)"
          % (len(baris), len(pdfs) - len(gagal), time.time() - t0))
    jns = {}
    for b in baris:
        jns[b["jenis"]] = jns.get(b["jenis"], 0) + 1
    kata = {}
    for b in baris:
        kata[b["jenis"]] = kata.get(b["jenis"], 0) + b["kata"]
    tot_kata = max(1, sum(kata.values()))
    print("  %-7s %6s %8s   %8s %8s" % ("jenis", "unit", "% unit", "kata", "% kata"))
    for k in ("prosa", "tabel", "gambar"):
        v, w = jns.get(k, 0), kata.get(k, 0)
        print("  %-7s %6d %7.1f%%   %8d %7.1f%%"
              % (k, v, 100.0 * v / len(baris), w, 100.0 * w / tot_kata))
    if gagal:
        print("\nBerkas gagal (%d):" % len(gagal))
        for x in gagal:
            print("   ", x)
    print("\nparagraf.csv  dan  Lembar_Pengodean.xlsx  sudah ditulis.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Argumen tidak lengkap."); sys.exit(1)
    utama(sys.argv[1])

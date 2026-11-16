import logging
import warnings

for _n in ("pdfminer", "pdfminer.pdfparser", "pdfminer.pdfdocument",
           "pdfminer.pdfpage", "pdfminer.pdfinterp", "pdfplumber", "pypdf",
           "PyPDF2"):
    logging.getLogger(_n).setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

import csv
import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("pdfplumber belum terpasang. Jalankan:  pip install pdfplumber")
    sys.exit(1)

try:
    from pypdf import PdfReader
    PUNYA_PYPDF = True
except ImportError:
    PUNYA_PYPDF = False


INTI = [
    "biodiversity", "biodiverse", "natural capital", "ecosystem services",
    "deforestation", "reforestation", "afforestation", "mangrove", "peatland",
    "wetland", "tnfd", "leap approach", "encore", "nature-related",
    "nature related", "nature-positive", "nature positive", "land use change",
    "habitat", "wildlife", "flora", "fauna", "species", "biosphere",
]

PINGGIRAN = [
    "nature", "ecosystem", "conservation", "restoration", "forest", "marine",
    "ocean", "coastal", "freshwater", "water stress", "water scarcity",
    "watershed", "soil", "pollution", "pollutant", "ecological", "ecology",
    "land use", "land-use",
]

IDIOM = [
    re.compile(r"\bnature\s+of\b", re.IGNORECASE),
    re.compile(r"\b(digital|business|national|financial|payment|innovation|"
               r"startup|broader|partner|banking|wider)\s+ecosystem\b", re.IGNORECASE),
    re.compile(r"\bwhole[- ]of[- ]ecosystem\b", re.IGNORECASE),
    re.compile(r"\bendorsement of forest certification\b", re.IGNORECASE),
    re.compile(r"\bforest stewardship council\b", re.IGNORECASE),
]

LEKSIKON = INTI + PINGGIRAN

MIN_KATA = 15
MAX_KATA = 220
LEBAR_GUTTER = 0.035

KODE = ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "B5"]
KETERANGAN_KODE = [
    ("A1", "Tata kelola alam"),
    ("A2", "Strategi: ketergantungan dan dampak"),
    ("A3", "Manajemen risiko dan dampak"),
    ("A4", "Metrik dan target alam"),
    ("B1", "Penyebutan kerangka dan keanggotaan"),
    ("B2", "Studi kasus transaksi klien"),
    ("B3", "Belanja lingkungan, CSR, dan filantropi"),
    ("B4", "Katalog produk dan riset"),
    ("B5", "Infrastruktur pasar dan proyek pihak ketiga"),
]

P_INTI = [re.compile(re.escape(k), re.IGNORECASE) for k in INTI]
P_PING = [re.compile(re.escape(k), re.IGNORECASE) for k in PINGGIRAN]
POLA = re.compile("|".join(re.escape(k) for k in LEKSIKON), re.IGNORECASE)


def lolos_saringan(teks: str):
    bersih = teks
    for p in IDIOM:
        bersih = p.sub(" ", bersih)
    n_inti = sum(1 for p in P_INTI if p.search(bersih))
    if n_inti:
        return True, n_inti
    n_ping = sum(1 for p in P_PING if p.search(bersih))
    return (n_ping >= 2), 0


def _peta_kolom(page):
    try:
        words = page.extract_words()
    except Exception:
        return None
    if len(words) < 40:
        return None

    lebar, tinggi = float(page.width), float(page.height)
    atas, bawah = tinggi * 0.06, tinggi * 0.96
    badan = [w for w in words if atas < w["top"] < bawah]
    if len(badan) < 40:
        return None

    N = 30
    h = (bawah - atas) / N
    pita = [[] for _ in range(N)]
    for w in badan:
        k = int((w["top"] - atas) / h)
        if 0 <= k < N:
            pita[k].append(w)
    terpakai = [k for k in range(N) if pita[k]]
    if len(terpakai) < 6:
        return None

    n_bin = int(lebar) + 1
    hitung = [0] * n_bin
    for k in terpakai:
        tanda = bytearray(n_bin)
        for w in pita[k]:
            for i in range(max(0, int(w["x0"])), min(n_bin - 1, int(w["x1"]) + 1)):
                tanda[i] = 1
        for i in range(n_bin):
            if tanda[i]:
                hitung[i] += 1

    ambang = max(1, int(len(terpakai) * 0.12))
    min_celah = max(5, int(lebar * 0.015))
    celah, i = [], 0
    while i < n_bin:
        if hitung[i] <= ambang:
            j = i
            while j < n_bin and hitung[j] <= ambang:
                j += 1
            if (j - i) >= min_celah:
                celah.append((i, j))
            i = j
        else:
            i += 1
    tengah = [(x, y) for x, y in celah if 0.32 * lebar < (x + y) / 2 < 0.68 * lebar]
    if not tengah:
        return None
    gx0, gx1 = max(tengah, key=lambda c: c[1] - c[0])

    bersih = []
    for k in range(N):
        if not pita[k]:
            bersih.append(True); continue
        ada = any(w["x0"] < gx1 and w["x1"] > gx0 for w in pita[k])
        bersih.append(not ada)

    terbaik, mulai = None, None
    for k in range(N + 1):
        ok = bersih[k] if k < N else False
        if ok and mulai is None:
            mulai = k
        elif not ok and mulai is not None:
            if terbaik is None or (k - mulai) > (terbaik[1] - terbaik[0]):
                terbaik = (mulai, k)
            mulai = None
    if terbaik is None or (terbaik[1] - terbaik[0]) < 6:
        return None

    y_awal = atas + terbaik[0] * h
    y_akhir = atas + terbaik[1] * h
    return ((gx0 + gx1) / 2.0, y_awal, y_akhir)


def teks_halaman(page):
    peta = _peta_kolom(page)
    if not peta:
        return page.extract_text() or ""
    potong, y0, y1 = peta
    lebar, tinggi = float(page.width), float(page.height)
    bagian = []

    def ambil(x0, ya, xb, yb):
        if yb - ya < 5:
            return
        try:
            t = page.crop((x0, ya, xb, yb)).extract_text() or ""
        except Exception:
            return
        if t.strip():
            bagian.append(t)

    ambil(0, 0, lebar, y0)
    ambil(0, y0, potong, y1)
    ambil(potong, y0, lebar, y1)
    ambil(0, y1, lebar, tinggi)

    if not bagian:
        return page.extract_text() or ""
    return "\n\n".join(bagian)


def baris_berulang(halaman_teks, ambang=0.30):
    from collections import Counter
    hit = Counter()
    for t in halaman_teks:
        for b in {x.strip() for x in t.split("\n") if x.strip()}:
            if len(b) <= 90:
                hit[b] += 1
    batas = max(3, int(len(halaman_teks) * ambang))
    return {b for b, n in hit.items() if n >= batas}


AKHIR_KALIMAT = re.compile(r"[.!?:;]\s*$")
AWAL_BARU = re.compile(r"^\s*(?:[•\-•]|\(?[a-z0-9]{1,3}[.)]\s|[A-Z])")


def jadi_paragraf(teks: str):
    baris = [b.strip() for b in teks.split("\n")]
    blok, kini = [], []
    for b in baris:
        if not b:
            if kini:
                blok.append(" ".join(kini)); kini = []
            continue
        kini.append(b)
        if AKHIR_KALIMAT.search(b) and len(" ".join(kini).split()) >= MIN_KATA:
            blok.append(" ".join(kini)); kini = []
    if kini:
        blok.append(" ".join(kini))
    return blok


def pecah_panjang(p: str):
    kata = p.split()
    if len(kata) <= MAX_KATA:
        return [p]
    kalimat = re.split(r"(?<=[.!?])\s+", p)
    hasil, kini = [], []
    for k in kalimat:
        kini.append(k)
        if len(" ".join(kini).split()) >= MAX_KATA:
            hasil.append(" ".join(kini)); kini = []
    if kini:
        hasil.append(" ".join(kini))
    return hasil


KENDALI = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def rapikan(p: str) -> str:
    p = KENDALI.sub(" ", p)
    p = re.sub(r"\s+", " ", p).strip()
    p = re.sub(r"(\w)-\s(\w)", r"\1\2", p)
    return p


def tulis_xlsx(baris, tujuan: Path):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.worksheet.datavalidation import DataValidation
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("openpyxl belum terpasang, lembar Excel dilewati. Jalankan: pip install openpyxl")
        return

    F = "Arial"
    wb = openpyxl.Workbook()

    ws = wb.active
    ws.title = "Pengodean"
    hdr = PatternFill("solid", fgColor="1F3864")
    yell = PatternFill("solid", fgColor="FFF2CC")
    t = Side(style="thin", color="D9D9D9")
    bd = Border(left=t, right=t, top=t, bottom=t)

    kolom = ["id", "negara", "bank", "tahun", "hal", "kata", "teks_paragraf",
             "kode", "kalimat_bukti", "catatan"]
    lebar = [7, 12, 14, 7, 6, 6, 95, 8, 40, 26]
    for i, (c, w) in enumerate(zip(kolom, lebar), 1):
        cell = ws.cell(row=1, column=i, value=c)
        cell.font = Font(name=F, size=10, bold=True, color="FFFFFF")
        cell.fill = hdr; cell.border = bd
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "H2"

    for r, b in enumerate(baris, start=2):
        vals = [b["id"], b["negara"], b["bank"], b["tahun"], b["hal"],
                b["kata"], b["teks"], "", "", ""]
        for i, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.font = Font(name=F, size=10)
            cell.border = bd
            cell.alignment = Alignment(vertical="top", wrap_text=(i in (7, 9, 10)))
            if i in (8, 9, 10):
                cell.fill = yell
        ws.row_dimensions[r].height = 58

    dv = DataValidation(type="list", formula1='"' + ",".join(KODE) + '"', allow_blank=True)
    dv.error = "Gunakan salah satu dari sembilan kode."
    ws.add_data_validation(dv)
    dv.add(f"H2:H{len(baris) + 1}")

    ws2 = wb.create_sheet("Kode")
    ws2["A1"] = "SEMBILAN KODE"
    ws2["A1"].font = Font(name=F, size=12, bold=True, color="1F3864")
    ws2["A3"] = "Tiga pertanyaan, dijawab berurutan:"
    ws2["A3"].font = Font(name=F, size=10, bold=True)
    for i, teks in enumerate([
        "1. Milik siapa objeknya? Portofolio, operasi, atau kebijakan bank sendiri -> lanjut. Proyek, klien, atau pihak lain -> Kelompok B.",
        "2. Apa jenis informasinya? Ketergantungan, dampak, proses penyaringan, target alam -> Kelompok A. Uang dibelanjakan, uang disalurkan, hitungan aktivitas -> Kelompok B.",
        "3. Apakah angkanya ikut berubah bila portofolio bank berubah? Bila tidak, tidak boleh A4.",
    ]):
        ws2.cell(row=4 + i, column=1, value=teks).font = Font(name=F, size=10)
    for i, (k, ket) in enumerate(KETERANGAN_KODE):
        ws2.cell(row=9 + i, column=1, value=k).font = Font(name=F, size=10, bold=True)
        ws2.cell(row=9 + i, column=2, value=ket).font = Font(name=F, size=10)
    ws2.column_dimensions["A"].width = 10
    ws2.column_dimensions["B"].width = 60

    wb.save(tujuan)


def main() -> None:
    if len(sys.argv) < 2:
        print("Argumen tidak lengkap."); return
    folder = Path(sys.argv[1]).expanduser()
    if not folder.is_dir():
        print("Folder tidak ditemukan."); return

    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        print("Tidak ada berkas PDF."); return

    baris, kosong, gagal = [], [], []
    nomor = 0

    for p in pdfs:
        bagian = p.stem.split("_")
        if len(bagian) < 3:
            gagal.append((p.name, "nama berkas tidak sesuai pola")); continue
        negara, bank, tahun = bagian[0], bagian[1], bagian[2]

        kandidat, halaman_total = [], 0
        cadangan = False
        try:
            with pdfplumber.open(str(p)) as pdf:
                halaman_total = len(pdf.pages)
                semua = []
                for page in pdf.pages:
                    try:
                        semua.append(teks_halaman(page) or "")
                    except Exception:
                        semua.append("")

            padat = sum(len(t) for t in semua) / max(1, halaman_total)
            if padat < 150 and PUNYA_PYPDF:
                try:
                    r = PdfReader(str(p))
                    if getattr(r, "is_encrypted", False):
                        try:
                            r.decrypt("")
                        except Exception:
                            pass
                    ulang = []
                    for hal in r.pages:
                        try:
                            ulang.append(hal.extract_text() or "")
                        except Exception:
                            ulang.append("")
                    if sum(len(t) for t in ulang) > sum(len(t) for t in semua):
                        semua = ulang
                        halaman_total = len(ulang)
                        cadangan = True
                except Exception:
                    pass

            if True:
                buang = baris_berulang(semua)
                for i, teks in enumerate(semua, start=1):
                    if not teks:
                        continue
                    bersih = "\n".join(b for b in teks.split("\n")
                                       if b.strip() not in buang)
                    for blok in jadi_paragraf(bersih):
                        for par in pecah_panjang(blok):
                            par = rapikan(par)
                            n = len(par.split())
                            if n < MIN_KATA:
                                continue
                            ok, n_inti = lolos_saringan(par)
                            if not ok:
                                continue
                            kandidat.append((i, par, n, n_inti))
        except Exception as e:
            gagal.append((p.name, type(e).__name__)); continue

        unik, terlihat = [], set()
        for hal, par, n, n_inti in kandidat:
            kunci = re.sub(r"\W+", "", par.lower())[:160]
            if kunci in terlihat:
                continue
            terlihat.add(kunci)
            unik.append((hal, par, n, n_inti))

        for hal, par, n, n_inti in unik:
            nomor += 1
            baris.append({"id": nomor, "negara": negara, "bank": bank,
                          "tahun": tahun, "hal": hal, "kata": n, "teks": par,
                          "inti": n_inti})

        tanda = "  [pypdf]" if cadangan else ""
        print(f"{p.name:<42} {halaman_total:>4} hal  ->  {len(unik):>4} paragraf{tanda}")
        if not unik:
            kosong.append(p.name)

    if not baris:
        print("\nTidak ada paragraf yang ditemukan.")
        return

    csv_out = folder / "paragraf_kandidat.csv"
    with csv_out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "negara", "bank", "tahun", "hal", "kata", "inti", "teks_paragraf"])
        for b in baris:
            w.writerow([b["id"], b["negara"], b["bank"], b["tahun"], b["hal"],
                        b["kata"], b["inti"], b["teks"]])

    print(f"\nTOTAL {len(baris)} paragraf dari {len(pdfs)} berkas")
    print(f"  {csv_out}")

    if kosong:
        print(f"\nBERKAS TANPA PARAGRAF ({len(kosong)}):")
        for n in kosong:
            print("  " + n)
    if gagal:
        print(f"\nBERKAS GAGAL DIBACA ({len(gagal)}):")
        for n, sebab in gagal:
            print(f"  {n}  <-  {sebab}")


if __name__ == "__main__":
    main()

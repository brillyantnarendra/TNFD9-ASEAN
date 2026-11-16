import csv
import random
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

try:
    import openpyxl
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.styles import Alignment, Font, PatternFill
except ImportError:
    print("openpyxl belum terpasang.  pip install openpyxl"); sys.exit(1)

BENIH = 20260913
AMBANG_SAMA = 0.95
BOBOT_BLOK = 2.6
BOBOT_AWAL = 1.8


def polos(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def periode(tahun):
    try:
        return "awal" if int(tahun) <= 2023 else "akhir"
    except ValueError:
        return "akhir"


def baca_kode_awal(xlsx):
    if not xlsx or not Path(xlsx).exists():
        return []
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    ws = wb["Pengodean"] if "Pengodean" in wb.sheetnames else wb[wb.sheetnames[0]]
    kep = [str(c.value).strip().lower() if c.value else "" for c in ws[1]]

    def idx(*n):
        for x in n:
            if x in kep:
                return kep.index(x)
        return None

    i_teks, i_kode = idx("teks_paragraf", "teks"), idx("kode")
    i_bukti, i_cat = idx("kalimat_bukti"), idx("catatan", "catatan_pengode")
    if i_teks is None:
        return []
    lama = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r[i_teks]:
            continue
        kode = str(r[i_kode] or "").strip() if i_kode is not None else ""
        cat = str(r[i_cat] or "").strip() if i_cat is not None else ""
        if not kode and not cat:
            continue
        lama.append(dict(teks=str(r[i_teks]), polos=polos(r[i_teks]), kode=kode,
                         bukti=str(r[i_bukti] or "") if i_bukti is not None else "",
                         catatan=cat))
    return lama


def cocokkan(teks, lama, indeks):
    p = polos(teks)
    kandidat = set()
    for k in (p[:40], p[40:80], p[-40:]):
        if len(k) >= 20:
            kandidat |= indeks.get(k[:20], set())
    terbaik, skor = None, 0.0
    for i in kandidat:
        s = SequenceMatcher(None, p, lama[i]["polos"], autojunk=False).ratio()
        if s > skor:
            terbaik, skor = lama[i], s
    return terbaik, skor


def utama(csv_korpus, xlsx_awal=None, jumlah=500):
    baris = list(csv.DictReader(open(csv_korpus, encoding="utf-8")))
    if not baris:
        print("Berkas kosong."); sys.exit(1)
    for b in baris:
        b["periode"] = periode(b["tahun"])
        b["lapis_jenis"] = "prosa" if b["jenis"] == "prosa" else "blok"
        b["strata"] = "%s|%s|%s" % (b["negara"], b["periode"], b["lapis_jenis"])

    sel = defaultdict(list)
    for b in baris:
        sel[b["strata"]].append(b)

    berat = {}
    for s, isi in sel.items():
        _, per, jns = s.split("|")
        f = 1.0
        if jns == "blok":
            f *= BOBOT_BLOK
        if per == "awal":
            f *= BOBOT_AWAL
        berat[s] = len(isi) * f
    total_berat = sum(berat.values())

    rng = random.Random(BENIH)
    sampel = []
    for s, isi in sorted(sel.items()):
        n = min(len(isi), max(1, int(round(jumlah * berat[s] / total_berat))))
        pilih = rng.sample(isi, n)
        p_pilih = n / len(isi)
        for b in pilih:
            b["p_pilih"] = round(p_pilih, 6)
            b["bobot"] = round(1.0 / p_pilih, 4)
            sampel.append(b)
    rng.shuffle(sampel)
    sampel.sort(key=lambda b: 0 if b["lapis_jenis"] == "blok" else 1)

    print("SAMPEL: %d baris dari %d kandidat\n" % (len(sampel), len(baris)))
    print("%-34s %6s %6s %8s" % ("strata", "punya", "ambil", "bobot"))
    for s in sorted(sel):
        amb = sum(1 for b in sampel if b["strata"] == s)
        if amb:
            print("%-34s %6d %6d %8.2f" % (s, len(sel[s]), amb, len(sel[s]) / amb))

    jns = defaultdict(int)
    for b in sampel:
        jns[b["jenis"]] += 1
    print("\njenis di sampel: " + "  ".join("%s %d (%.1f%%)" %
          (k, v, 100.0 * v / len(sampel)) for k, v in sorted(jns.items())))
    per = defaultdict(int)
    for b in sampel:
        per[b["periode"]] += 1
    print("periode di sampel: " + "  ".join("%s %d (%.1f%%)" %
          (k, v, 100.0 * v / len(sampel)) for k, v in sorted(per.items())))

    lama = baca_kode_awal(xlsx_awal)
    n_bawa = 0
    if lama:
        indeks = defaultdict(set)
        for i, l in enumerate(lama):
            p = l["polos"]
            for k in (p[:40], p[40:80], p[-40:]):
                if len(k) >= 20:
                    indeks[k[:20]].add(i)
        for b in sampel:
            cocok, skor = cocokkan(b["teks"], lama, indeks)
            if cocok and skor >= AMBANG_SAMA:
                b["kode_awal"] = cocok["kode"]
                b["bukti_awal"] = cocok["bukti"]
                b["catatan_awal"] = cocok["catatan"]
                b["kemiripan"] = round(skor, 3)
                n_bawa += 1
            else:
                b["kode_awal"] = b["bukti_awal"] = b["catatan_awal"] = ""
                b["kemiripan"] = round(skor, 3) if cocok else 0.0
        print("\nKODE LAMA YANG TERBAWA: %d dari %d  = %.1f%%"
              % (n_bawa, len(sampel), 100.0 * n_bawa / len(sampel)))
        print("  SISA DIKODE: %d baris" % (len(sampel) - n_bawa))
    else:
        for b in sampel:
            b["kode_awal"] = b["bukti_awal"] = b["catatan_awal"] = ""
            b["kemiripan"] = 0.0
        print("\nLembar awal tidak diberikan atau kosong; tidak ada kode yang dibawa.")

    kol = ["id", "negara", "bank", "tahun", "periode", "hal", "jenis", "bagian",
           "strata", "p_pilih", "bobot", "kata", "inti", "kemiripan", "teks",
           "kode_awal", "bukti_awal", "catatan_awal"]
    with open("sampel.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=kol)
        w.writeheader()
        for b in sampel:
            w.writerow({k: b.get(k, "") for k in kol})

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pengodean"
    kepala = ["id", "negara", "bank", "tahun", "hal", "jenis", "bagian", "kata",
              "inti", "bobot", "teks_paragraf", "kode", "kalimat_bukti", "catatan"]
    ws.append(kepala)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DCE6F1")
    kuning = PatternFill("solid", fgColor="FFF2CC")
    for b in sampel:
        ws.append([b["id"], b["negara"], b["bank"], b["tahun"], b["hal"],
                   b["jenis"], b.get("bagian", ""), b["kata"], b["inti"],
                   b["bobot"], b["teks"], b["kode_awal"], b["bukti_awal"],
                   b["catatan_awal"]])
        if b["kode_awal"] or b["catatan_awal"]:
            for c in range(12, 15):
                ws.cell(ws.max_row, c).fill = kuning
    lebar = dict(A=7, B=11, C=13, D=7, E=6, F=8, G=7, H=6, I=6, J=8, K=95,
                 L=9, M=52, N=24)
    for k, v in lebar.items():
        ws.column_dimensions[k].width = v
    for r in range(2, ws.max_row + 1):
        ws.cell(r, 11).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(r, 13).alignment = Alignment(wrap_text=True, vertical="top")
    if ws.max_row >= 2:
        dv = DataValidation(type="list", allow_blank=True,
                            formula1='"A1,A2,A3,A4,B1,B2,B3,B4,B5"')
        ws.add_data_validation(dv)
        dv.add("L2:L%d" % ws.max_row)
    ws.freeze_panes = "A2"

    inf = wb.create_sheet("Keterangan")
    for a, b in [
        ("Baris berlatar kuning", "kode dibawa dari lembar awal karena teks "
         "paragrafnya tidak berubah. Tidak perlu dikode ulang."),
        ("Baris putih", "harus dikode dari awal."),
        ("jenis = prosa", "paragraf naratif biasa."),
        ("jenis = tabel", "satu tabel utuh; baca kepala kolomnya lebih dahulu."),
        ("jenis = gambar", "teks di dalam infografis; urutannya melintang, "
         "baca sebagai daftar, bukan kalimat. Panah dan susunan tidak ikut, "
         "jadi A1 kerap tidak dapat ditegakkan dari teks gambar saja."),
        ("bagian", "potongan ke berapa dari satu tabel panjang, misalnya 2/5. "
         "Kepala kolom diulang di setiap potongan, jadi potongan itu berdiri "
         "sendiri dan tidak perlu dicari sambungannya."),
        ("Urutan baris", "tabel dan gambar lebih dahulu, lalu prosa teracak. "
         "Pengodean berurutan dari atas; berhenti di tengah "
         "bagian prosa tetap meninggalkan sampel yang sah."),
        ("bobot", "kebalikan peluang terpilih. Dipakai untuk menghitung angka "
         "tingkat korpus. Tidak dipakai saat mengode."),
    ]:
        inf.append([a, b])
    inf.column_dimensions["A"].width = 24
    inf.column_dimensions["B"].width = 90
    wb.save("Lembar_Pengodean_SAMPEL.xlsx")

    n_blok = sum(1 for b in sampel if b["lapis_jenis"] == "blok")
    print("\nLembar_Pengodean_SAMPEL.xlsx  dan  sampel.csv  sudah ditulis.")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print("Argumen tidak lengkap."); sys.exit(1)
    utama(a[0], a[1] if len(a) > 1 else None, int(a[2]) if len(a) > 2 else 500)

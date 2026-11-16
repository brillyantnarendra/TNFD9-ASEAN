import csv, sys, random, collections
from pathlib import Path

try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:
    print("openpyxl belum terpasang.  python -m pip install openpyxl")
    sys.exit(1)

N_LATIHAN = 30
N_KAPPA = 100
BENIH = 20260920

NAMA = ("coder2", "coder3")


def periode(tahun):
    try:
        t = int(str(tahun)[:4])
    except (TypeError, ValueError):
        return "akhir"
    return "awal" if t <= 2023 else "akhir"


def baca_csv(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tulis(nama, baris, judul):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = judul

    kol = ["id", "bank", "tahun", "hal", "jenis", "teks_paragraf",
           "kode", "kalimat_bukti", "catatan"]
    ws.append(kol)
    for c in ws[1]:
        c.font = Font(bold=True)

    for b in baris:
        ws.append([b["id"], b.get("bank", ""), b.get("tahun", ""),
                   b.get("hal", ""), b.get("jenis", ""),
                   b.get("teks") or b.get("teks_paragraf", ""), "", "", ""])

    for kolom, lebar in zip("ABCDEFGHI", [8, 14, 8, 7, 9, 95, 10, 55, 24]):
        ws.column_dimensions[kolom].width = lebar
    kuning = PatternFill("solid", fgColor="FFF2CC")
    for r in range(2, ws.max_row + 1):
        ws.cell(r, 6).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(r, 8).alignment = Alignment(wrap_text=True, vertical="top")
        for c in (7, 8, 9):
            ws.cell(r, c).fill = kuning
    ws.freeze_panes = "A2"

    bantu = wb.create_sheet("Pilihan")
    for i, v in enumerate(["Rusak", "Rusak, pulih-manual", "Bukan alam",
                           "Bukan alam, iklim", "Ragu - anteseden hilang"], start=1):
        bantu.cell(i, 1, v)
    bantu.sheet_state = "hidden"

    akhir = ws.max_row
    dv_kode = DataValidation(type="list",
                             formula1='"A1,A2,A3,A4,B1,B2,B3,B4,B5"',
                             allow_blank=True)
    dv_cat = DataValidation(type="list",
                            formula1="=Pilihan!$A$1:$A$5", allow_blank=True)
    ws.add_data_validation(dv_kode); dv_kode.add("G2:G%d" % akhir)
    ws.add_data_validation(dv_cat);  dv_cat.add("I2:I%d" % akhir)

    wb.save(str(nama))
    print("  %-40s %3d baris" % (nama, len(baris)))


def beri_strata(baris):
    for b in baris:
        lapis = "prosa" if b.get("jenis") == "prosa" else "blok"
        b["strata"] = "%s|%s|%s" % (b.get("negara", "?"),
                                    periode(b.get("tahun")), lapis)
    return baris


def tarik(baris, n, acak):
    sel = collections.defaultdict(list)
    for b in baris:
        sel[b["strata"]].append(b)
    kunci = sorted(sel)
    dasar = {s: max(1, round(n * len(sel[s]) / len(baris))) for s in kunci}
    while sum(dasar.values()) > n:
        s = max(kunci, key=lambda k: dasar[k]); dasar[s] -= 1
    while sum(dasar.values()) < n:
        s = min(kunci, key=lambda k: dasar[k]); dasar[s] += 1
    ambil = []
    for s in kunci:
        isi = sel[s][:]
        acak.shuffle(isi)
        ambil += isi[:min(dasar[s], len(isi))]
    acak.shuffle(ambil)
    return ambil[:n]


def sebaran(judul, baris):
    print("\n%s" % judul)
    hit = collections.Counter(b["strata"] for b in baris)
    for s in sorted(hit):
        print("  %-34s %3d" % (s, hit[s]))
    jns = collections.Counter(b.get("jenis") for b in baris)
    print("  jenis: " + "  ".join("%s %d" % kv for kv in sorted(jns.items())))


def utama(csv_korpus, csv_sampel, benih=BENIH):
    korpus = beri_strata(baca_csv(csv_korpus))
    sampel = beri_strata(baca_csv(csv_sampel))

    dipakai = {str(b["id"]) for b in sampel}
    luar = [b for b in korpus if str(b["id"]) not in dipakai]
    print("korpus %d baris, sampel %d baris, di luar sampel %d baris."
          % (len(korpus), len(sampel), len(luar)))

    acak = random.Random(benih)
    kappa = tarik(sampel, N_KAPPA, acak)
    latihan = tarik(luar, N_LATIHAN, acak)

    tumpang = {str(b["id"]) for b in kappa} & {str(b["id"]) for b in latihan}
    assert not tumpang, "latihan dan kappa tidak boleh beririsan"

    sebaran("sebaran strata — 100 baris kappa (dari dalam 501)", kappa)
    sebaran("sebaran strata — 30 baris latihan (dari luar 501)", latihan)

    print("\nberkas yang ditulis")
    for n, nama in (("2", NAMA[0]), ("3", NAMA[1])):
        map_ = Path("Pengode_%s_%s" % (n, nama))
        map_.mkdir(exist_ok=True)
        tulis(map_ / ("Latihan_30_%s.xlsx" % nama), latihan, "Latihan")
        tulis(map_ / ("Kappa_100_%s.xlsx" % nama), kappa, "Kappa")

    with open("kunci_baris_keandalan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["blok", "asal", "urutan", "id", "bank", "tahun", "hal",
                    "jenis", "strata"])
        for nama, asal, blok in (("kappa", "dalam-501", kappa),
                                 ("latihan", "luar-501", latihan)):
            for i, b in enumerate(blok, 1):
                w.writerow([nama, asal, i, b["id"], b.get("bank", ""),
                            b.get("tahun", ""), b.get("hal", ""),
                            b.get("jenis", ""), b["strata"]])
    print("  %-40s daftar id" % "kunci_baris_keandalan.csv")

    with open("peta_pengode.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sebutan", "nama"])
        w.writerow(["Pengode 2", NAMA[0]])
        w.writerow(["Pengode 3", NAMA[1]])
    print("  %-40s nama Pengode 2 dan 3" % "peta_pengode.csv")
    print("\nbenih acak %d."
          % benih)


if __name__ == "__main__":
    arg = sys.argv[1:]
    posisi, benih, i = [], BENIH, 0
    while i < len(arg):
        if arg[i] == "--benih" and i + 1 < len(arg):
            benih = int(arg[i + 1]); i += 2
        elif arg[i] == "--nama" and i + 1 < len(arg):
            n = [x.strip() for x in arg[i + 1].split(",") if x.strip()]
            if len(n) != 2:
                print("--nama butuh dua nama dipisah koma, misal  --nama coder2,coder3")
                sys.exit(1)
            NAMA = (n[0], n[1]); i += 2
        else:
            posisi.append(arg[i]); i += 1
    if len(posisi) != 2:
        print("Argumen tidak lengkap."); sys.exit(1)
    utama(posisi[0], posisi[1], benih)

import sys
import csv
import random
from collections import defaultdict

KOLOM_ID = None
KOLOM_TAHUN = None
KOLOM_BOBOT = None
KOLOM_BANK = None
ULANGAN = 2000
BENIH = 20261003

KELAS = ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "B5",
         "bukan alam", "bukan alam, iklim", "rusak", "rusak, pulih-manual"]
GRUP_A = {"A1", "A2", "A3", "A4"}
GRUP_B = {"B1", "B2", "B3", "B4", "B5"}
PEMBAGIAN = {
    "UTAMA (2021-23 vs 2024-25)": lambda t: "awal" if t <= 2023 else "akhir",
    "SENSITIF (2021-22 vs 2023-25)": lambda t: "awal" if t <= 2022 else "akhir",
}


def baca(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        kepala = next(r)
        return kepala, [b for b in r if b]


def cari(kepala, kata, nama_set):
    if nama_set is not None:
        return kepala.index(nama_set) if nama_set in kepala else None
    cocok = [i for i, k in enumerate(kepala) if any(w in k.lower() for w in kata)]
    return cocok[0] if len(cocok) == 1 else None


def ukuran(unit):
    hasil = {}
    for p in ("awal", "akhir"):
        sub = [(lab, w) for lab, per, w in unit if per == p]
        tot = sum(w for _, w in sub)
        if tot == 0:
            return None
        d = {k: sum(w for lab, w in sub if lab == k) / tot for k in KELAS}
        d["Grup A"] = sum(d[k] for k in GRUP_A)
        d["Grup B"] = sum(d[k] for k in GRUP_B)
        d["Gerbang"] = 1 - d["Grup A"] - d["Grup B"]
        alam = d["Grup A"] + d["Grup B"]
        d["A/(A+B)"] = d["Grup A"] / alam if alam > 0 else float("nan")
        hasil[p] = d
    return hasil


def main():
    if len(sys.argv) < 3:
        print("Pakai: py komposisi_periode.py banding_5model_501.csv sampel.csv")
        return
    kb, bb = baca(sys.argv[1])
    ks, bs = baca(sys.argv[2])
    print("Gold diambil dari kolom: %r (kolom ke-2 %s)" % (kb[1], sys.argv[1]))
    gold = {b[0].strip(): b[1].strip() for b in bb}

    if KOLOM_ID is not None:
        i_id = ks.index(KOLOM_ID)
    else:
        skor = [sum(1 for b in bs if b[i].strip() in gold) for i in range(len(ks))]
        i_id = max(range(len(ks)), key=lambda i: skor[i])
        if skor[i_id] < 0.95 * len(gold):
            i_id = None
    i_th = cari(ks, ["tahun", "year"], KOLOM_TAHUN)
    i_w = cari(ks, ["bobot", "weight"], KOLOM_BOBOT)
    i_bk = cari(ks, ["bank"], KOLOM_BANK)

    if None in (i_id, i_th, i_w, i_bk):
        print("!! Kolom belum bisa ditentukan otomatis:")
        for nama, i in [("ID", i_id), ("TAHUN", i_th), ("BOBOT", i_w), ("BANK", i_bk)]:
            print("   %-6s -> %s" % (nama, ks[i] if i is not None else "TIDAK DITEMUKAN / LEBIH DARI SATU"))
        print("Kolom yang ada di %s:" % sys.argv[2])
        for k in ks:
            print("   ", k)
        return
    print("Kolom dipakai: id=%r, tahun=%r, bobot=%r, bank=%r"
          % (ks[i_id], ks[i_th], ks[i_w], ks[i_bk]))

    data = []
    for b in bs:
        uid = b[i_id].strip()
        if uid in gold:
            data.append((uid, gold[uid], int(float(b[i_th])), float(b[i_w]), b[i_bk].strip()))
    tak_dikenal = {d[1] for d in data if d[1] not in KELAS}
    if tak_dikenal:
        print("!! Label gold di luar daftar: %s" % ", ".join(sorted(tak_dikenal)))
        return

    print("\n== PEMERIKSAAN ==")
    print("Unit cocok          : %d (harus 501)" % len(data))
    print("Jumlah bobot        : %.1f" % sum(d[3] for d in data))
    print("Jumlah bank         : %d (harus 19)" % len({d[4] for d in data}))
    per_th = defaultdict(int)
    for d in data:
        per_th[d[2]] += 1
    print("Unit per tahun      : %s (harus 2021:64, 2022:88, 2023:118, 2024:93, 2025:138)"
          % ", ".join("%d:%d" % (t, per_th[t]) for t in sorted(per_th)))

    rng = random.Random(BENIH)
    bank_ke_unit = defaultdict(list)
    for d in data:
        bank_ke_unit[d[4]].append(d)
    daftar_bank = sorted(bank_ke_unit)

    baris_csv = []
    for nama, fungsi in PEMBAGIAN.items():
        unit = [(d[1], fungsi(d[2]), d[3]) for d in data]
        n_awal = sum(1 for u in unit if u[1] == "awal")
        n_akhir = len(unit) - n_awal
        dasar = ukuran(unit)

        sim = defaultdict(list)
        for _ in range(ULANGAN):
            pilih = [rng.choice(daftar_bank) for _ in daftar_bank]
            u = [(d[1], fungsi(d[2]), d[3]) for bk in pilih for d in bank_ke_unit[bk]]
            h = ukuran(u)
            if h is None:
                continue
            for k in KELAS + ["Grup A", "Grup B", "Gerbang", "A/(A+B)"]:
                sim[(k, "awal")].append(h["awal"][k])
                sim[(k, "akhir")].append(h["akhir"][k])
                sim[(k, "selisih")].append(h["akhir"][k] - h["awal"][k])

        def sk(v):
            v = sorted(x for x in v if x == x)
            return v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]

        print("\n== %s ==   n awal = %d, n akhir = %d (unit sampel)" % (nama, n_awal, n_akhir))
        print("%-20s %8s %8s %9s   %s" % ("Kelas (berbobot)", "awal", "akhir", "selisih", "SK 95% selisih (klaster bank)"))
        for k in ["Grup A", "Grup B", "Gerbang", "A/(A+B)"] + KELAS:
            a, z = dasar["awal"][k], dasar["akhir"][k]
            lo, hi = sk(sim[(k, "selisih")])
            tanda = "  *" if (lo > 0 or hi < 0) else ""
            print("%-20s %7.1f%% %7.1f%% %+8.1f pp   [%+.1f, %+.1f]%s"
                  % (k, 100 * a, 100 * z, 100 * (z - a), 100 * lo, 100 * hi, tanda))
            if k == "A/(A+B)":
                print("-" * 78)
            baris_csv.append([nama, k, round(a, 4), round(z, 4), round(z - a, 4), round(lo, 4), round(hi, 4)])

    print("\n== PER TAHUN BUKU (berbobot, deskriptif) ==")
    print("%-6s %6s %8s %8s %8s %9s" % ("Tahun", "n", "Grup A", "B1", "Gerbang", "A/(A+B)"))
    for t in sorted(per_th):
        sub = [(d[1], d[3]) for d in data if d[2] == t]
        tot = sum(w for _, w in sub)
        ga = sum(w for lab, w in sub if lab in GRUP_A) / tot
        gb = sum(w for lab, w in sub if lab in GRUP_B) / tot
        b1 = sum(w for lab, w in sub if lab == "B1") / tot
        print("%-6d %6d %7.1f%% %7.1f%% %7.1f%% %8.1f%%"
              % (t, len(sub), 100 * ga, 100 * b1, 100 * (1 - ga - gb), 100 * ga / (ga + gb)))
        baris_csv.append(["PER TAHUN", str(t), round(ga, 4), round(b1, 4), round(1 - ga - gb, 4), round(ga / (ga + gb), 4), ""])

    with open("komposisi_periode_hasil.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pembagian", "kelas", "awal_atau_GrupA", "akhir_atau_B1", "selisih_atau_Gerbang", "SK_bawah_atau_A/(A+B)", "SK_atas"])
        w.writerows(baris_csv)
    print("\n* = selang 95% tidak memuat nol.")
    print("Ditulis: komposisi_periode_hasil.csv")


if __name__ == "__main__":
    main()

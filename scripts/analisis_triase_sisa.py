import csv
import sys
from collections import Counter

from alat_analisis import Catat, grup, baca_banding, baca_bobot, wilson, GERBANG, REASONING


def kelas(lbl):
    if grup(lbl) == "A":
        return "Group A"
    if lbl == "B1":
        return "B1"
    if grup(lbl) == "B":
        return "B lain (B2-B5)"
    return "gerbang"


def main():
    if len(sys.argv) != 3:
        print("Argumen tidak lengkap.")
        return
    ids, gold, lab = baca_banding(sys.argv[1])
    w = baca_bobot(sys.argv[2], ids)
    log = Catat("hasil_triase_sisa.txt")
    unit = []
    for u in ids:
        ls = [lab[n][u] for n in REASONING]
        top, cnt = Counter(ls).most_common(1)[0]
        unit.append({"id": u, "w": w[u], "gold": gold[u], "sepakat": cnt == 3, "label": top})
    log("Unit %d, bobot %.1f, disepakati 3/3: %d" % (len(unit), sum(x["w"] for x in unit),
                                                     sum(x["sepakat"] for x in unit)))
    aturan = [
        ("R1 tidak disepakati", lambda x: not x["sepakat"]),
        ("R2 R1 + sepakat A3", lambda x: (not x["sepakat"]) or x["label"] == "A3"),
        ("R3 R1 + sepakat gerbang", lambda x: (not x["sepakat"]) or x["label"] in GERBANG),
        ("R4 R1 + A3 + gerbang", lambda x: (not x["sepakat"]) or x["label"] == "A3" or x["label"] in GERBANG),
    ]
    hasil = []
    for nama, f in aturan:
        terima = [x for x in unit if not f(x)]
        log("\n" + "=" * 70 + "\n%s — label diterima: %d unit" % (nama, len(terima)))
        log("   %-16s %4s %6s %10s %16s %12s" % ("label otomatis", "n", "salah", "% salah", "SK Wilson 95%", "% salah bobot"))
        for k in ("Group A", "B1", "B lain (B2-B5)", "gerbang", "SEMUA"):
            isi = terima if k == "SEMUA" else [x for x in terima if kelas(x["label"]) == k]
            if not isi:
                log("   %-16s %4d" % (k, 0))
                continue
            s = [x for x in isi if x["label"] != x["gold"]]
            lo, hi = wilson(len(s), len(isi))
            ws = sum(x["w"] for x in s) / sum(x["w"] for x in isi)
            log("   %-16s %4d %6d %9.1f%% [%5.1f, %5.1f] %11.1f%%"
                % (k, len(isi), len(s), 100 * len(s) / len(isi), 100 * lo, 100 * hi, 100 * ws))
            hasil.append([nama, k, len(isi), len(s), round(len(s) / len(isi), 4), round(lo, 4), round(hi, 4), round(ws, 4)])
            if k in ("Group A", "B1") and s:
                log("        salah terbanyak (gold -> otomatis):",
                    ", ".join("%s->%s %d" % (a, b, c) for (a, b), c in Counter((x["gold"], x["label"]) for x in s).most_common(4)))
        lew = [x for x in terima if grup(x["gold"]) == "A" and grup(x["label"]) != "A"]
        tot_a = sum(1 for x in unit if grup(x["gold"]) == "A")
        log("   Pilar terlewat (gold A, diterima dengan label bukan A): %d dari %d unit pilar" % (len(lew), tot_a))
        hasil.append([nama, "pilar_terlewat", tot_a, len(lew), round(len(lew) / tot_a, 4), "", "", ""])

    with open("hasil_triase_sisa.csv", "w", newline="", encoding="utf-8") as fo:
        wr = csv.writer(fo)
        wr.writerow(["aturan", "label_otomatis", "n", "n_salah", "tingkat_salah", "wilson_bawah", "wilson_atas", "tingkat_salah_bobot"])
        wr.writerows(hasil)
    log("\nDitulis juga: hasil_triase_sisa.csv")
    log.tutup()


if __name__ == "__main__":
    main()

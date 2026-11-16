import csv
import sys
from collections import Counter

from alat_analisis import Catat, grup, baca_banding, kappa, bootstrap_kappa, RUN


def main():
    if len(sys.argv) != 2:
        print("Argumen tidak lengkap.")
        return
    ids, gold, lab = baca_banding(sys.argv[1])
    log = Catat("hasil_kelompok_ab.txt")
    g = [grup(gold[u]) for u in ids]
    log("Unit: %d | gold A=%d B=%d G=%d" % (len(ids), g.count("A"), g.count("B"), g.count("G")))
    hasil = []
    for nama, _ in RUN:
        m = [grup(lab[nama][u]) for u in ids]
        log("\n" + "=" * 64 + "\n" + nama + "\n" + "=" * 64)
        t = Counter(zip(g, m))
        log("   gold\\model      A      B      G")
        for x in "ABG":
            log("   %-10s %6d %6d %6d" % (x, t[(x, "A")], t[(x, "B")], t[(x, "G")]))
        ak3 = sum(1 for x, y in zip(g, m) if x == y) / len(g)
        k3 = kappa(g, m)
        lo3, hi3 = bootstrap_kappa(g, m)
        log("   Tiga kelompok: akurasi %.3f | kappa %.3f [%.3f, %.3f]" % (ak3, k3, lo3, hi3))

        gb = ["A" if x == "A" else "N" for x in g]
        mb = ["A" if x == "A" else "N" for x in m]
        tp = sum(1 for x, y in zip(gb, mb) if x == "A" and y == "A")
        fp = sum(1 for x, y in zip(gb, mb) if x == "N" and y == "A")
        fn = sum(1 for x, y in zip(gb, mb) if x == "A" and y == "N")
        pr = tp / (tp + fp) if tp + fp else float("nan")
        rc = tp / (tp + fn) if tp + fn else float("nan")
        f1 = 2 * pr * rc / (pr + rc) if pr + rc else float("nan")
        kb = kappa(gb, mb)
        log("   Pilar vs bukan: presisi A %.3f | recall A %.3f | F1 A %.3f | kappa %.3f" % (pr, rc, f1, kb))

        ab = [(x, y) for x, y in zip(g, m) if x in "AB" and y in "AB"]
        kab = kappa([x for x, _ in ab], [y for _, y in ab])
        log("   Hanya A/B di keduanya (n=%d): kappa A vs B %.3f" % (len(ab), kab))
        log("   Jumlah A: model %d vs gold %d (selisih %+d)" % (m.count("A"), g.count("A"), m.count("A") - g.count("A")))
        hasil.append([nama, round(ak3, 4), round(k3, 4), round(lo3, 4), round(hi3, 4),
                      round(pr, 4), round(rc, 4), round(f1, 4), round(kb, 4),
                      len(ab), round(kab, 4), m.count("A"), g.count("A")])

    with open("hasil_kelompok_ab.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["run", "akurasi_3kel", "kappa_3kel", "sk_bawah", "sk_atas", "presisi_A",
                    "recall_A", "F1_A", "kappa_A_vs_bukan", "n_AB", "kappa_A_vs_B", "jumlah_A_model", "jumlah_A_gold"])
        w.writerows(hasil)
    log("\nDitulis juga: hasil_kelompok_ab.csv")
    log.tutup()


if __name__ == "__main__":
    main()

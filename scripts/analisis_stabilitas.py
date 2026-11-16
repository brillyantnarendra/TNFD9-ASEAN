import csv
import glob
import itertools
import re
import sys
from collections import Counter

from alat_analisis import Catat, norm, grup, baca_banding, baca_bobot, kappa, RUN, REASONING

BERKAS_RUN = {"GPT-6 Astra*": "gpt", "Gemini 3.8 Flash*": "gemini", "DeepSeek V4 (T)*": "dsthink",
              "DeepSeek V4": "ds", "Command A": "cohere"}
KELAS = {"A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "B5"}


def baca_ulang(path):
    out, galat = {}, 0
    with open(path, newline="", encoding="utf-8") as f:
        for b in csv.DictReader(f):
            if b.get("galat"):
                galat += 1
                continue
            kode = (b.get("code") or "").strip()
            lab = kode if kode in KELAS else (b.get("note") or "").strip()
            out[str(b["id"]).strip()] = norm(lab)
    return out, galat


def macro_f1(gold, pred):
    cnt = Counter(gold.values())
    f1 = []
    for c, n in cnt.items():
        if n < 10:
            continue
        tp = sum(1 for u in pred if gold[u] == c and pred[u] == c)
        fp = sum(1 for u in pred if gold[u] != c and pred[u] == c)
        fn = sum(1 for u in pred if gold[u] == c and pred[u] != c)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1.append(2 * p * r / (p + r) if p + r else 0.0)
    return sum(f1) / len(f1)


AWAL = {"2021", "2022", "2023"}


def porsi_a(pred, w, tahun):
    hasil = {}
    for per in ("awal", "akhir"):
        uu = [u for u in pred if (tahun[u] in AWAL) == (per == "awal")]
        a = sum(w[u] for u in uu if grup(pred[u]) == "A")
        tot = sum(w[u] for u in uu)
        hasil[per] = a / tot if tot else float("nan")
    return hasil["awal"], hasil["akhir"], hasil["akhir"] - hasil["awal"]


def main():
    if len(sys.argv) != 3:
        print("Argumen tidak lengkap.")
        return
    ids, gold, lab = baca_banding(sys.argv[1])
    w = baca_bobot(sys.argv[2], ids)
    with open(sys.argv[2], newline="", encoding="utf-8-sig") as f:
        tahun = {b["id"].strip(): b["tahun"].strip() for b in csv.DictReader(f)}
    log = Catat("hasil_stabilitas.txt")
    hasil = []
    rata_akurasi = {}

    for nama, _ in RUN:
        ulang = {1: dict(lab[nama])}
        catatan = {1: "run asli (banding_5model_501.csv)"}
        for p in sorted(glob.glob("Ulang_%s_r*.csv" % BERKAS_RUN[nama])):
            m = re.search(r"_r(\d+)\.csv$", p)
            if not m or "kering" in p:
                continue
            d, g = baca_ulang(p)
            ulang[int(m.group(1))] = d
            catatan[int(m.group(1))] = "%s (%d unit, %d galat)" % (p, len(d), g)
        log("\n" + "=" * 76 + "\n" + nama + "\n" + "=" * 76)
        for k in sorted(ulang):
            log("   ulangan %d: %s" % (k, catatan[k]))
        if len(ulang) < 2:
            log("   (belum ada ulangan; dilewati)")
            continue

        log("\n   %-8s %5s %8s %7s %8s %7s %6s %22s"
            % ("ulangan", "n", "akurasi", "kappa", "macroF1", "gerbang", "B1>A3", "porsi A awal/akhir/beda"))
        akur, kap = [], []
        for k in sorted(ulang):
            pr = {u: ulang[k][u] for u in ids if u in ulang[k]}
            ak = sum(1 for u in pr if pr[u] == gold[u]) / len(pr)
            kp = kappa([gold[u] for u in pr], [pr[u] for u in pr])
            mf = macro_f1({u: gold[u] for u in pr}, pr)
            gb = sum(1 for u in pr if grup(pr[u]) == "G")
            ba = sum(1 for u in pr if gold[u] == "B1" and pr[u] == "A3")
            a0, a1, da = porsi_a(pr, w, tahun)
            akur.append(ak)
            kap.append(kp)
            log("   %-8d %5d %8.3f %7.3f %8.3f %7d %6d   %5.1f%% / %5.1f%% / %+5.1f"
                % (k, len(pr), ak, kp, mf, gb, ba, 100 * a0, 100 * a1, 100 * da))
            hasil.append([nama, "ulangan_%d" % k, len(pr), round(ak, 4), round(kp, 4), round(mf, 4),
                          gb, ba, round(a0, 4), round(a1, 4), round(da, 4), "", ""])
        rata_akurasi[nama] = sum(akur) / len(akur)
        log("   rentang akurasi %.3f | rentang kappa %.3f" % (max(akur) - min(akur), max(kap) - min(kap)))

        log("\n   Antar-ulangan:")
        for i, j in itertools.combinations(sorted(ulang), 2):
            uu = [u for u in ids if u in ulang[i] and u in ulang[j]]
            beda = sum(1 for u in uu if ulang[i][u] != ulang[j][u])
            kij = kappa([ulang[i][u] for u in uu], [ulang[j][u] for u in uu])
            log("   ulangan %d vs %d: n=%d | label berubah %d (%.1f%%) | kappa antar-ulangan %.3f"
                % (i, j, len(uu), beda, 100 * beda / len(uu), kij))
            hasil.append([nama, "u%d_vs_u%d" % (i, j), len(uu), "", round(kij, 4), "", "", "", "", "", "",
                          beda, round(beda / len(uu), 4)])

    r = [n for n in REASONING if n in rata_akurasi]
    if len(r) >= 2:
        sel = max(rata_akurasi[n] for n in r) - min(rata_akurasi[n] for n in r)
        log("\nSelisih akurasi rata-rata terbesar antar konfigurasi penalaran: %.3f" % sel)
        for n in r:
            log("   %-20s rata-rata akurasi %.3f" % (n, rata_akurasi[n]))

    with open("hasil_stabilitas.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["run", "bagian", "n", "akurasi", "kappa", "macroF1", "gerbang", "B1_ke_A3",
                     "porsiA_awal", "porsiA_akhir", "porsiA_beda", "label_berubah", "proporsi_berubah"])
        wr.writerows(hasil)
    log("\nDitulis juga: hasil_stabilitas.csv")
    log.tutup()


if __name__ == "__main__":
    main()

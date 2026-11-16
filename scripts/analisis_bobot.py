import csv
import sys
from collections import Counter, defaultdict

from alat_analisis import Catat

AWAL = {"2021", "2022", "2023"}


def strata_kandidat(b):
    per = "awal" if b["tahun"] in AWAL else "akhir"
    jen = "prosa" if b["jenis"] == "prosa" else "blok"
    return "%s|%s|%s" % (b["negara"], per, jen)


def main():
    if len(sys.argv) != 3:
        print("Argumen tidak lengkap.")
        return
    with open(sys.argv[1], newline="", encoding="utf-8-sig") as f:
        kand = list(csv.DictReader(f))
    with open(sys.argv[2], newline="", encoding="utf-8-sig") as f:
        samp = list(csv.DictReader(f))
    log = Catat("hasil_bobot.txt")
    log("Kandidat: %d | sampel: %d | jumlah bobot sampel: %.1f"
        % (len(kand), len(samp), sum(float(b["bobot"]) for b in samp)))

    Nh = Counter(strata_kandidat(b) for b in kand)
    nh = Counter(b["strata"] for b in samp)
    cek = Counter(b["strata"] for b in samp if strata_kandidat(b) != b["strata"])
    if cek:
        log("!! Definisi strata di skrip ini tidak cocok dengan kolom strata pada %d unit sampel: %s"
            % (sum(cek.values()), dict(cek)))
    log("\nBAGIAN 1. Strata (negara | periode | jenis)")
    log("  %-28s %6s %6s %8s %8s %10s" % ("strata", "N", "n", "p=n/N", "bobot", "cek kolom"))
    baris = []
    for s in sorted(set(Nh) | set(nh)):
        bobot_kolom = sorted({round(float(b["bobot"]), 4) for b in samp if b["strata"] == s})
        p = nh[s] / Nh[s] if Nh[s] else float("nan")
        bw = 1 / p if p else float("nan")
        ok = "ok" if bobot_kolom and all(abs(x - bw) < 0.01 for x in bobot_kolom) else str(bobot_kolom)
        log("  %-28s %6d %6d %8.3f %8.3f %10s" % (s, Nh[s], nh[s], p, bw, ok))
        baris.append([s, Nh[s], nh[s], round(p, 6), round(bw, 4), ok])
    tanpa = [s for s in Nh if nh[s] == 0]
    if tanpa:
        log("  Strata tanpa unit sampel: %s" % tanpa)
    with open("tabel_strata.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["strata", "N_kandidat", "n_sampel", "p_terpilih", "bobot", "cek"])
        wr.writerows(baris)

    th = sorted({b["tahun"] for b in kand})
    neg = sorted({b["negara"] for b in kand})
    ck = Counter((b["negara"], b["tahun"]) for b in kand)
    cs = Counter((b["negara"], b["tahun"]) for b in samp)
    log("\nBAGIAN 2. Kandidat / sampel per negara dan tahun")
    log("  %-12s " % "negara" + " ".join("%11s" % t for t in th) + "%13s" % "total")
    for n in neg:
        log("  %-12s " % n + " ".join("%5d / %3d " % (ck[(n, t)], cs[(n, t)]) for t in th)
            + "%7d / %3d" % (sum(ck[(n, t)] for t in th), sum(cs[(n, t)] for t in th)))
    log("  %-12s " % "TOTAL" + " ".join("%5d / %3d " % (sum(ck[(n, t)] for n in neg), sum(cs[(n, t)] for n in neg)) for t in th)
        + "%7d / %3d" % (len(kand), len(samp)))

    bk = Counter((b["negara"], b["bank"], b["tahun"]) for b in kand)
    bs = Counter((b["negara"], b["bank"], b["tahun"]) for b in samp)
    bank = sorted({(b["negara"], b["bank"]) for b in kand})
    with open("tabel_bank_tahun.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["negara", "bank"] + ["kandidat_%s" % t for t in th] + ["sampel_%s" % t for t in th]
                    + ["kandidat_total", "sampel_total"])
        for n, b in bank:
            wr.writerow([n, b] + [bk[(n, b, t)] for t in th] + [bs[(n, b, t)] for t in th]
                        + [sum(bk[(n, b, t)] for t in th), sum(bs[(n, b, t)] for t in th)])
    log("\nBAGIAN 3. Bank dengan unit sampel: %d dari %d bank"
        % (len({(n, b) for (n, b, _) in bs}), len(bank)))
    nol = [b for (n, b) in bank if sum(bs[(n, b, t)] for t in th) == 0]
    log("  Bank tanpa unit sampel: %s" % nol)
    log("  Rincian bank x tahun ditulis ke tabel_bank_tahun.csv")
    log.tutup()


if __name__ == "__main__":
    main()

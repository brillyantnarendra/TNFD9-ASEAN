import csv
import sys

from alat_analisis import Catat, grup, baca_banding, baca_bobot, RUN, REASONING

AWAL = {"2021", "2022", "2023"}


def main():
    if len(sys.argv) != 3:
        print("Argumen tidak lengkap.")
        return
    ids, gold, lab = baca_banding(sys.argv[1])
    w = baca_bobot(sys.argv[2], ids)
    with open(sys.argv[2], newline="", encoding="utf-8-sig") as f:
        meta = {b["id"].strip(): b for b in csv.DictReader(f)}
    log = Catat("hasil_b1_a3.txt")

    contoh = []
    for u in ids:
        if gold[u] != "B1":
            continue
        n = sum(1 for r in REASONING if lab[r][u] == "A3")
        if n >= 2:
            contoh.append((n, u))
    contoh.sort(key=lambda x: (-x[0], int(x[1])))
    log("BAGIAN 1. Gold B1 yang dilabeli A3 oleh >=2 dari 3 run penalaran: %d unit" % len(contoh))
    for n, u in contoh:
        m = meta[u]
        t = " ".join(m["teks"].split())
        log("\n  id %s | %s %s %s | %s | %d/3 run -> A3" % (u, m["negara"], m["bank"], m["tahun"], m["jenis"], n))
        log("  " + (t[:420] + (" ..." if len(t) > 420 else "")))
    with open("contoh_B1_A3.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["id", "negara", "bank", "tahun", "jenis", "run_salah_dari_3",
                     "GPT", "Gemini", "DS_T", "DS", "CmdA", "teks", "tipe_kesalahan"])
        for n, u in contoh:
            m = meta[u]
            wr.writerow([u, m["negara"], m["bank"], m["tahun"], m["jenis"], n]
                        + [lab[r][u] for r, _ in RUN] + [" ".join(m["teks"].split()), ""])

    log("\n\nBAGIAN 2. Dampak pada porsi Group A (berbobot; poin persentase dari SEMUA unit periode itu)")
    for per, th in (("SEMUA", None), ("TB2021-2023", True), ("TB2024-2025", False)):
        uu = [u for u in ids if th is None or ((meta[u]["tahun"] in AWAL) == th)]
        W = sum(w[u] for u in uu)
        ga = sum(w[u] for u in uu if grup(gold[u]) == "A") / W
        log("\n  Periode %s | porsi A gold %.1f%%" % (per, 100 * ga))
        log("  %-20s %8s %8s %9s %9s %9s %9s %10s"
            % ("run", "porsi A", "selisih", "+B1->A", "+B1->A3", "+Blain->A", "+G->A", "-A hilang"))
        for r, _ in RUN:
            ma = sum(w[u] for u in uu if grup(lab[r][u]) == "A") / W
            b1a = sum(w[u] for u in uu if gold[u] == "B1" and grup(lab[r][u]) == "A") / W
            b1a3 = sum(w[u] for u in uu if gold[u] == "B1" and lab[r][u] == "A3") / W
            bla = sum(w[u] for u in uu if grup(gold[u]) == "B" and gold[u] != "B1" and grup(lab[r][u]) == "A") / W
            gab = sum(w[u] for u in uu if grup(gold[u]) == "G" and grup(lab[r][u]) == "A") / W
            hil = sum(w[u] for u in uu if grup(gold[u]) == "A" and grup(lab[r][u]) != "A") / W
            log("  %-20s %7.1f%% %+7.1f %+9.1f %+9.1f %+9.1f %+9.1f %+10.1f"
                % (r, 100 * ma, 100 * (ma - ga), 100 * b1a, 100 * b1a3, 100 * bla, 100 * gab, -100 * hil))
    log("\n  selisih = (+B1->A) + (+Blain->A) + (+G->A) + (-A hilang). Kolom +B1->A3 adalah bagian dari +B1->A.")
    log("\nDitulis juga: contoh_B1_A3.csv")
    log.tutup()


if __name__ == "__main__":
    main()

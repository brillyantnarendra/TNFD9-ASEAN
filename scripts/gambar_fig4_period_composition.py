import sys
import csv
import random
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

KOLOM_ID = None
KOLOM_TAHUN = None
KOLOM_BOBOT = None
KOLOM_BANK = None
LAPORAN = {2021: 18, 2022: 18, 2023: 20, 2024: 20, 2025: 20}
AWAL = {2021, 2022, 2023}
ULANGAN = 2000
BENIH = 20261003
MODEL_GAMBAR = [("deepseek_think.csv", "Thinking on"),
                ("deepseek.csv", "Thinking off")]
KELUAR_GAMBAR = "fig4_period_composition"

GRUP_A = {"A1", "A2", "A3", "A4"}
GRUP_B = {"B1", "B2", "B3", "B4", "B5"}


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


def bagian(unit, j, tahun_set):
    sub = [u for u in unit if u["th"] in tahun_set]
    tot = sum(u["w"] for u in sub)
    a = sum(u["w"] for u in sub if u["lab"][j] in GRUP_A)
    b = sum(u["w"] for u in sub if u["lab"][j] in GRUP_B)
    return a / tot, (a / (a + b) if a + b > 0 else float("nan"))


def per_laporan(unit, j, tahun_set):
    lap = sum(LAPORAN[t] for t in tahun_set)
    a = sum(u["w"] for u in unit if u["th"] in tahun_set and u["lab"][j] in GRUP_A) / lap
    b = sum(u["w"] for u in unit if u["th"] in tahun_set and u["lab"][j] in GRUP_B) / lap
    return a, b


def main():
    if len(sys.argv) < 3:
        print("Pakai: py gambar_fig4_period_composition.py banding_5model_501.csv sampel.csv")
        return
    kb, bb = baca(sys.argv[1])
    ks, bs = baca(sys.argv[2])
    nama = ["GOLD"] + kb[2:]
    lab = {b[0].strip(): [x.strip() for x in b[1:]] for b in bb}

    if KOLOM_ID is not None:
        i_id = ks.index(KOLOM_ID)
    else:
        skor = [sum(1 for b in bs if b[i].strip() in lab) for i in range(len(ks))]
        i_id = max(range(len(ks)), key=lambda i: skor[i])
    i_th = cari(ks, ["tahun", "year"], KOLOM_TAHUN)
    i_w = cari(ks, ["bobot", "weight"], KOLOM_BOBOT)
    i_bk = cari(ks, ["bank"], KOLOM_BANK)
    if None in (i_th, i_w, i_bk):
        print("!! Kolom tidak terdeteksi")
        return

    unit = []
    for b in bs:
        uid = b[i_id].strip()
        if uid in lab:
            unit.append({"th": int(float(b[i_th])), "w": float(b[i_w]),
                         "bk": b[i_bk].strip(), "lab": lab[uid]})
    AKHIR = set(LAPORAN) - AWAL
    print("Unit: %d, bobot: %.1f, model: %d" % (len(unit), sum(u["w"] for u in unit), len(nama) - 1))
    kosong = [(nama[j], sum(1 for u in unit if not u["lab"][j])) for j in range(len(nama))]
    for n, k in kosong:
        if k:
            print("   %s: %d label kosong" % (n, k))

    print("\n== GAMBARAN KORPUS PER SUMBER LABEL (pembagian utama TB2021-23 vs TB2024-25) ==")
    print("%-34s %15s %15s %13s %13s" % ("Sumber", "Grup A %", "A/(A+B) %", "A/lap.", "B/lap."))
    hasil = []
    for j, n in enumerate(nama):
        a0, r0 = bagian(unit, j, AWAL)
        a1, r1 = bagian(unit, j, AKHIR)
        pa0, pb0 = per_laporan(unit, j, AWAL)
        pa1, pb1 = per_laporan(unit, j, AKHIR)
        print("%-34s %6.1f->%6.1f %6.1f->%6.1f %5.1f->%5.1f %5.1f->%5.1f"
              % (n[-34:], 100 * a0, 100 * a1, 100 * r0, 100 * r1, pa0, pa1, pb0, pb1))
        hasil.append([n, a0, a1, r0, r1, pa0, pa1, pb0, pb1, pa1 / pa0, pb1 / pb0])
    print("\nRasio pertumbuhan per laporan (akhir / awal):")
    for h in hasil:
        print("   %-34s Grup A x%.2f   Grup B x%.2f" % (h[0][-34:], h[9], h[10]))

    rng = random.Random(BENIH)
    bank_ke_unit = defaultdict(list)
    for u in unit:
        bank_ke_unit[u["bk"]].append(u)
    daftar = sorted(bank_ke_unit)
    sim = defaultdict(list)
    for _ in range(ULANGAN):
        s = [u for bk in (rng.choice(daftar) for _ in daftar) for u in bank_ke_unit[bk]]
        try:
            g0, gr0 = bagian(s, 0, AWAL)
            g1, gr1 = bagian(s, 0, AKHIR)
        except ZeroDivisionError:
            continue
        for j in range(1, len(nama)):
            m0, mr0 = bagian(s, j, AWAL)
            m1, mr1 = bagian(s, j, AKHIR)
            sim[(j, "A")].append((m1 - m0) - (g1 - g0))
            sim[(j, "R")].append((mr1 - mr0) - (gr1 - gr0))
            sim[(j, "lvA")].append(((m0 + m1) - (g0 + g1)) / 2)

    def sk(v):
        v = sorted(x for x in v if x == x)
        return v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]

    print("\n== BIAS MODEL TERHADAP GOLD (SK 95% klaster bank) ==")
    print("Bias tingkat = rata-rata (model - gold) Grup A % di kedua periode")
    print("Bias tren    = (perubahan model) - (perubahan gold); nol = tren gold terulang")
    print("%-34s %24s %24s %24s" % ("Model", "bias tingkat Grup A", "bias tren Grup A", "bias tren A/(A+B)"))
    for j in range(1, len(nama)):
        g = hasil[0]
        m = hasil[j]
        tingkat = ((m[1] + m[2]) - (g[1] + g[2])) / 2
        trenA = (m[2] - m[1]) - (g[2] - g[1])
        trenR = (m[4] - m[3]) - (g[4] - g[3])
        lt = sk(sim[(j, "lvA")])
        la = sk(sim[(j, "A")])
        lr = sk(sim[(j, "R")])
        print("%-34s %+6.1f [%+5.1f,%+5.1f] %+6.1f [%+5.1f,%+5.1f] %+6.1f [%+5.1f,%+5.1f]"
              % (nama[j][-34:], 100 * tingkat, 100 * lt[0], 100 * lt[1],
                 100 * trenA, 100 * la[0], 100 * la[1], 100 * trenR, 100 * lr[0], 100 * lr[1]))
        hasil[j] += [tingkat, lt[0], lt[1], trenA, la[0], la[1], trenR, lr[0], lr[1]]

    with open("komposisi_model_hasil.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sumber", "A_awal", "A_akhir", "AAB_awal", "AAB_akhir", "Alap_awal", "Alap_akhir",
                    "Blap_awal", "Blap_akhir", "rasio_A", "rasio_B", "bias_tingkat", "bt_lo", "bt_hi",
                    "bias_trenA", "ba_lo", "ba_hi", "bias_trenAAB", "br_lo", "br_hi"])
        for h in hasil:
            w.writerow([h[0]] + [round(x, 4) for x in h[1:]])

    idx_gambar = []
    for pola, tampil in MODEL_GAMBAR:
        c = [j for j, n in enumerate(nama) if j > 0 and n.lower().endswith(pola)]
        if len(c) != 1:
            print("!! Kolom berakhiran %r ditemukan %d kali; Fig. 4 tidak dibuat." % (pola, len(c)))
            return
        idx_gambar.append((c[0], tampil))

    plt.rcParams.update({"font.family": "serif",
                         "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
                         "font.size": 7, "pdf.fonttype": 42, "ps.fonttype": 42})
    th = sorted(LAPORAN)
    fig, ax = plt.subplots(1, 2, figsize=(3.5, 1.75), sharex=True)
    biru = plt.get_cmap("Blues")
    gaya = [(0, "Human gold standard", "-", "o", biru(0.95))] + \
           [(j, t, s, m, c) for (j, t), s, m, c in zip(idx_gambar, ["--", ":"], ["s", "^"], [biru(0.70), biru(0.45)])]
    for p, grup, judul in [(0, GRUP_A, "(a) Pillar content (Group A)"),
                           (1, GRUP_B, "(b) Nature talk (Group B)")]:
        for j, t, s, m, c in gaya:
            y = [sum(u["w"] for u in unit if u["th"] == x and u["lab"][j] in grup) / LAPORAN[x] for x in th]
            ax[p].plot(th, y, linestyle=s, marker=m, markersize=2.6, linewidth=0.9, color=c, label=t)
        ax[p].set_title(judul, fontsize=7)
        ax[p].set_xticks(th)
        ax[p].set_xticklabels(["'%02d" % (x % 100) for x in th])
        ax[p].tick_params(labelsize=6, width=0.5, length=2)
        ax[p].set_ylim(bottom=0)
        for sisi in ("top", "right"):
            ax[p].spines[sisi].set_visible(False)
        for sisi in ("left", "bottom"):
            ax[p].spines[sisi].set_linewidth(0.5)
    ax[0].set_ylabel("Est. units per report", fontsize=6.5)
    fig.text(0.55, 0.01, "Fiscal year", ha="center", fontsize=6.5)
    h, l = ax[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=3, fontsize=6, frameon=False, handlelength=2.6, columnspacing=1.2, bbox_to_anchor=(0.55, 1.0))
    fig.tight_layout(rect=(0, 0.04, 1, 0.88), w_pad=1.0)
    fig.savefig(KELUAR_GAMBAR + ".pdf")
    fig.savefig(KELUAR_GAMBAR + ".png", dpi=300)
    print("\nDitulis: komposisi_model_hasil.csv, %s.pdf, %s.png" % (KELUAR_GAMBAR, KELUAR_GAMBAR))


if __name__ == "__main__":
    main()

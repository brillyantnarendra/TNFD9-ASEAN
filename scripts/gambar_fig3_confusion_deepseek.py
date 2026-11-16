import sys
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

LABEL_TAMPIL = {
    "A1": "A1", "A2": "A2", "A3": "A3", "A4": "A4",
    "B1": "B1", "B2": "B2", "B3": "B3", "B4": "B4", "B5": "B5",
    "bukan alam": "NN",
    "bukan alam, iklim": "NN-C",
    "rusak": "GB",
    "rusak, pulih-manual": "GB",
}
URUTAN = ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "B5",
          "bukan alam", "bukan alam, iklim", "rusak", "rusak, pulih-manual"]
GERBANG = ["bukan alam", "bukan alam, iklim", "rusak", "rusak, pulih-manual"]
SOROT = ("B1", "A3")
PETA_WARNA = "Blues"
GARIS_SEL = 0.8
JUDUL_PANEL = ["(a) Thinking disabled", "(b) Thinking enabled"]
CARI_KOLOM = ["deepseek.csv", "deepseek_think.csv"]
KELUAR = "fig3_confusion_deepseek"


def main():
    if len(sys.argv) < 2:
        print("Pakai: py gambar_fig3_confusion_deepseek.py banding_5model_501.csv")
        return
    with open(sys.argv[1], newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        kepala = next(r)
        baris = [b for b in r if b]

    idx = []
    for pola in CARI_KOLOM:
        cocok = [i for i, k in enumerate(kepala) if k.lower().endswith(pola)]
        if len(cocok) != 1:
            print("!! Kolom berakhiran %r ditemukan %d kali. Kolom tersedia:" % (pola, len(cocok)))
            for k in kepala:
                print("   ", k)
            return
        idx.append(cocok[0])
    print("Panel (a): %s" % kepala[idx[0]])
    print("Panel (b): %s" % kepala[idx[1]])

    emas = [b[1] for b in baris]
    duga = [[b[i] for b in baris] for i in idx]

    tak_dikenal = {v for v in emas + duga[0] + duga[1] if v and v not in URUTAN}
    if tak_dikenal:
        print("!! Label di luar daftar URUTAN: %s" % ", ".join(sorted(tak_dikenal)))
        return

    rows = [k for k in URUTAN if k in set(emas)]
    cols = [k for k in URUTAN if k in set(emas) | set(duga[0]) | set(duga[1])]

    mat = []
    for d in duga:
        m = [[0] * len(cols) for _ in rows]
        kosong = 0
        for g, p in zip(emas, d):
            if not p:
                kosong += 1
                continue
            m[rows.index(g)][cols.index(p)] += 1
        mat.append((m, kosong))

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 7, "axes.linewidth": 0.5,
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })
    fig, axes = plt.subplots(2, 1, figsize=(3.5, 6.0), constrained_layout=True)

    for ax, (m, kosong), judul in zip(axes, mat, JUDUL_PANEL):
        prop = [[v / max(1, sum(rw)) for v in rw] for rw in m]
        im = ax.imshow(prop, cmap=PETA_WARNA, vmin=0, vmax=1, aspect="auto")
        for i, rw in enumerate(m):
            for j, v in enumerate(rw):
                if v:
                    ax.text(j, i, str(v), ha="center", va="center", fontsize=6,
                            color="white" if prop[i][j] > 0.55 else "black")
        ax.set_xticks(range(len(cols)))
        ax.set_xticklabels([LABEL_TAMPIL[c] for c in cols], rotation=90)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([LABEL_TAMPIL[c] for c in rows])
        ax.tick_params(length=0, pad=2)
        if GARIS_SEL:
            ax.set_xticks([x - 0.5 for x in range(len(cols) + 1)], minor=True)
            ax.set_yticks([y - 0.5 for y in range(len(rows) + 1)], minor=True)
            ax.grid(which="minor", color="white", linewidth=GARIS_SEL)
            ax.tick_params(which="minor", length=0)
        ax.set_xlabel("Model label")
        ax.set_title(judul, fontsize=8, pad=4)
        for s in ax.spines.values():
            s.set_linewidth(0.4)

        if SOROT[0] in rows and SOROT[1] in cols:
            i, j = rows.index(SOROT[0]), cols.index(SOROT[1])
            ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False,
                                   lw=1.4, ec="black", zorder=4))
        gc = [cols.index(g) for g in GERBANG if g in cols]
        if gc:
            ax.add_patch(Rectangle((min(gc) - 0.5, -0.5), len(gc), len(rows),
                                   fill=False, lw=0.9, ls=(0, (3, 2)), ec="black",
                                   zorder=4))

        benar = sum(m[i][cols.index(k)] for i, k in enumerate(rows) if k in cols)
        n = sum(sum(rw) for rw in m)
        print("%s : tepat %d dari %d dinilai (label kosong/tak sah: %d)"
              % (judul, benar, n, kosong))

    for ax in axes:
        ax.set_ylabel("Human gold standard label")
    cb = fig.colorbar(im, ax=axes, orientation="horizontal", shrink=0.75, pad=0.01, aspect=35)
    cb.set_label("Row proportion", fontsize=7)
    cb.ax.tick_params(labelsize=6, length=2, width=0.4)
    cb.outline.set_linewidth(0.4)

    fig.savefig(KELUAR + ".pdf")
    fig.savefig(KELUAR + ".png", dpi=300)
    print("Ditulis: %s.pdf dan %s.png" % (KELUAR, KELUAR))


if __name__ == "__main__":
    main()

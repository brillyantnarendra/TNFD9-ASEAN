import sys
import csv
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SUMBER = [
    (None, "Human gold standard"),
    ("hasil_model_gpt.csv", "GPT-6 Astra*"),
    ("gemini.csv", "Gemini 3.8 Flash*"),
    ("deepseek_think.csv", "DeepSeek V4 (T)*"),
    ("deepseek.csv", "DeepSeek V4"),
    ("cohere.csv", "Command A"),
]
PETA_WARNA = "Blues"
KELUAR = "fig2_kappa_runs"


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe)


def main():
    if len(sys.argv) < 2:
        print("Pakai: py gambar_fig2_kappa_runs.py banding_5model_501.csv")
        return
    with open(sys.argv[1], newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        kepala = next(r)
        baris = [b for b in r if b]

    kolom = []
    for pola, nama in SUMBER:
        if pola is None:
            kolom.append((1, nama))
            continue
        cocok = [i for i, k in enumerate(kepala) if i >= 2 and k.lower().endswith(pola.lower())]
        if len(cocok) != 1:
            print("!! Kolom berakhiran %r ditemukan %d kali. Kolom tersedia:" % (pola, len(cocok)))
            for k in kepala:
                print("   ", k)
            return
        kolom.append((cocok[0], nama))
    print("Unit: %d" % len(baris))
    for i, nama in kolom:
        print("  %-18s <- %s" % (nama, kepala[i]))

    lab = [[b[i].strip() for b in baris] for i, _ in kolom]
    nama = [n for _, n in kolom]
    k = len(lab)
    M = [[kappa(lab[i], lab[j]) if i != j else 1.0 for j in range(k)] for i in range(k)]

    print("\nKappa Cohen (501 unit):")
    print(" " * 19 + "".join("%9s" % n[:8] for n in nama))
    for i in range(k):
        print("%-19s" % nama[i] + "".join("%9.3f" % M[i][j] for j in range(k)))

    plt.rcParams.update({"font.family": "serif",
                         "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
                         "font.size": 7, "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, ax = plt.subplots(figsize=(3.5, 2.55))
    vmin, vmax = 0.4, 0.9
    cmap = plt.get_cmap(PETA_WARNA)
    for i in range(k):
        for j in range(i):
            v = M[i][j]
            warna = cmap((v - vmin) / (vmax - vmin))
            ax.add_patch(plt.Rectangle((j, k - 1 - i), 1, 1, facecolor=warna,
                                       edgecolor="white", linewidth=1.0))
            gelap = (v - vmin) / (vmax - vmin) > 0.55
            ax.text(j + 0.5, k - 1 - i + 0.5, ("%.2f" % v)[1:] if v < 1 else "1.00",
                    ha="center", va="center", fontsize=7,
                    color="white" if gelap else "black")
    ax.plot([1, 1], [0, k - 1], color="black", linewidth=0.6)
    ax.plot([4, 4], [0, k - 4], color="black", linewidth=0.6, linestyle="--")
    ax.plot([1, 4], [k - 4, k - 4], color="black", linewidth=0.6, linestyle="--")
    ax.set_xlim(0, k - 1)
    ax.set_ylim(0, k - 1)
    ax.set_xticks([j + 0.5 for j in range(k - 1)])
    ax.set_xticklabels([n.replace("Human gold standard", "Human gold\nstandard") for n in nama[:-1]],
                       rotation=35, ha="right", fontsize=6.5)
    ax.set_yticks([k - 1 - i + 0.5 for i in range(1, k)])
    ax.set_yticklabels(nama[1:], fontsize=6.5)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin, vmax))
    cb = fig.colorbar(sm, ax=ax, fraction=0.045, pad=0.03)
    cb.set_label("Cohen's $\\kappa$", fontsize=6.5)
    cb.ax.tick_params(labelsize=6, length=2)
    cb.outline.set_linewidth(0.4)
    fig.tight_layout(pad=0.3)
    fig.savefig(KELUAR + ".pdf")
    fig.savefig(KELUAR + ".png", dpi=300)
    print("\nDitulis: %s.pdf dan %s.png" % (KELUAR, KELUAR))


if __name__ == "__main__":
    main()

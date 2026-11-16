import sys
import csv
import math
import random
import itertools


def mcnemar_eksak(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    ekor = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * ekor)


def main():
    if len(sys.argv) < 2:
        print("Pakai: py uji_berpasangan.py banding_3model_501.csv")
        return
    path = sys.argv[1]
    ulang = 5000
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        kepala = next(r)
        baris = [b for b in r if b]
    model = kepala[2:]
    print("Berkas : %s" % path)
    print("Model  : %s" % ", ".join(model))
    print()

    acak = random.Random(20260928)
    for i, j in itertools.combinations(range(len(model)), 2):
        pas = []
        for b in baris:
            emas, x, y = b[1], b[2 + i], b[2 + j]
            if not emas or not x or not y:
                continue
            pas.append((x == emas, y == emas))
        n = len(pas)
        if not n:
            continue
        acc_x = sum(p[0] for p in pas) / n
        acc_y = sum(p[1] for p in pas) / n
        bb = sum(1 for p in pas if p[0] and not p[1])
        cc = sum(1 for p in pas if p[1] and not p[0])
        p = mcnemar_eksak(bb, cc)

        selisih = []
        for _ in range(ulang):
            s = [pas[acak.randrange(n)] for _ in range(n)]
            selisih.append((sum(t[0] for t in s) - sum(t[1] for t in s)) / n)
        selisih.sort()
        lo = selisih[int(0.025 * ulang)]
        hi = selisih[int(0.975 * ulang) - 1]

        print("%s  vs  %s   (n=%d)" % (model[i], model[j], n))
        print("  akurasi               : %.4f  vs  %.4f" % (acc_x, acc_y))
        print("  selisih               : %+.4f   SK95%% [%+.4f, %+.4f]"
              % (acc_x - acc_y, lo, hi))
        print("  hanya kiri benar (b)  : %d" % bb)
        print("  hanya kanan benar (c) : %d" % cc)
        print("  McNemar eksak p       : %.4g" % p)
        print()
    k = len(model) * (len(model) - 1) // 2
    print("%d pasangan diuji; ambang Bonferroni" % k)
    print("0.05/%d = %.4f." % (k, 0.05 / k))


if __name__ == "__main__":
    main()

import csv
import sys
from collections import Counter

from alat_analisis import Catat, norm, baca_banding, kappa, bootstrap_kappa, RUN


def main():
    if len(sys.argv) != 3:
        print("Argumen tidak lengkap.")
        return
    with open(sys.argv[1], newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        kepala = next(r)
        baris = [b for b in r if b]

    def kolom(kata):
        c = [i for i, k in enumerate(kepala) if kata.lower() in k.lower()]
        if len(c) != 1:
            print("!! Kolom memuat %r ditemukan %d kali: %s" % (kata, len(c), kepala))
            sys.exit(1)
        return c[0]

    i_utama, i_p2, i_p3 = kolom("Lembar_Pengodean"), kolom("coder2"), kolom("coder3")
    kod = {}
    for b in baris:
        kod[b[0].strip()] = {"utama": norm(b[i_utama]), "p2": norm(b[i_p2]), "p3": norm(b[i_p3])}
    nama_p = {"utama": "coder1", "p2": "coder2", "p3": "coder3"}

    ids, gold, lab = baca_banding(sys.argv[2])
    log = Catat("hasil_mayoritas_koder.txt")
    hasil = []

    sama = [u for u in ids if u in kod]
    beda = [u for u in sama if kod[u]["utama"] != gold[u]]
    log("A. Unit di banding_5model_100: %d, ditemukan di label_per_unit: %d" % (len(ids), len(sama)))
    log("   Label coder1 BERBEDA dari kolom emas: %d unit %s"
        % (len(beda), beda[:10] if beda else ""))
    if len(sama) != len(ids):
        log("!! Tidak semua unit cocok.")

    maj, tanpa = {}, []
    for u in sama:
        c = Counter(kod[u].values()).most_common(1)[0]
        if c[1] >= 2:
            maj[u] = c[0]
        else:
            tanpa.append(u)
    log("\nB. Label mayoritas tiga pengode")
    log("   Unit dengan mayoritas: %d | tanpa mayoritas (dikeluarkan): %d" % (len(maj), len(tanpa)))
    beda_maj = sum(1 for u in maj if maj[u] != kod[u]["utama"])
    log("   Unit yang label mayoritasnya BERBEDA dari coder1: %d" % beda_maj)
    log("   Sebaran label mayoritas:", dict(Counter(maj.values()).most_common()))
    u_maj = [u for u in ids if u in maj]
    log("\n   %-20s %4s %8s %22s %18s" % ("Run", "n", "akurasi", "kappa vs mayoritas [SK]", "kappa vs coder1"))
    for nama, _ in RUN:
        a = [lab[nama][u] for u in u_maj]
        m = [maj[u] for u in u_maj]
        g = [kod[u]["utama"] for u in u_maj]
        ak = sum(1 for x, y in zip(a, m) if x == y) / len(a)
        k = kappa(a, m)
        lo, hi = bootstrap_kappa(a, m)
        kg = kappa(a, g)
        log("   %-20s %4d %8.3f %8.3f [%.3f, %.3f] %12.3f" % (nama, len(a), ak, k, lo, hi, kg))
        hasil.append(["B_mayoritas", nama, len(a), round(ak, 4), round(k, 4), round(lo, 4), round(hi, 4), round(kg, 4)])
    for p in ("p2", "p3"):
        a = [kod[u][p] for u in u_maj]
        m = [maj[u] for u in u_maj]
        log("   %-20s %4d %8.3f %8.3f"
            % (nama_p[p][:20], len(a), sum(1 for x, y in zip(a, m) if x == y) / len(a), kappa(a, m)))

    log("\nC. Sensitivitas: unit tanpa mayoritas diputus oleh coder1 (n = %d)" % len(sama))
    maj2 = {u: maj.get(u, kod[u]["utama"]) for u in sama}
    for nama, _ in RUN:
        a = [lab[nama][u] for u in sama]
        m = [maj2[u] for u in sama]
        k = kappa(a, m)
        log("   %-20s kappa %.3f  akurasi %.3f" % (nama, k, sum(1 for x, y in zip(a, m) if x == y) / len(a)))
        hasil.append(["C_putus_utama", nama, len(a), "", round(k, 4), "", "", ""])

    log("\nD. Tolok ukur setara (acuan = dua pengode lain yang sepakat)")
    for p in ("utama", "p2", "p3"):
        lain = [q for q in ("utama", "p2", "p3") if q != p]
        uu = [u for u in ids if u in kod and kod[u][lain[0]] == kod[u][lain[1]]]
        ref = [kod[u][lain[0]] for u in uu]
        kh = kappa([kod[u][p] for u in uu], ref)
        log("   Acuan tanpa %-18s n=%3d | %s: kappa %.3f" % (nama_p[p], len(uu), nama_p[p], kh))
        hasil.append(["D_acuan_tanpa_" + p, nama_p[p], len(uu), "", round(kh, 4), "", "", ""])
        for nama, _ in RUN:
            km = kappa([lab[nama][u] for u in uu], ref)
            log("        %-20s kappa %.3f" % (nama, km))
            hasil.append(["D_acuan_tanpa_" + p, nama, len(uu), "", round(km, 4), "", "", ""])

    with open("hasil_mayoritas_koder.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bagian", "pengode_atau_run", "n", "akurasi", "kappa", "sk_bawah", "sk_atas", "kappa_vs_utama"])
        w.writerows(hasil)
    log("\nDitulis juga: hasil_mayoritas_koder.csv")
    log.tutup()


if __name__ == "__main__":
    main()

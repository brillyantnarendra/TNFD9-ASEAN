import csv
import json
import os
import sys
import time
from pathlib import Path

try:
    import uji_asap
except ImportError:
    print("uji_asap.py tidak ditemukan.")
    sys.exit(1)

JSONL = "hasil_model.jsonl"
CSV = "hasil_model.csv"


def _sudah_ada(path):
    ada = set()
    if not Path(path).exists():
        return ada
    with open(path, encoding="utf-8") as f:
        for garis in f:
            garis = garis.strip()
            if not garis:
                continue
            try:
                d = json.loads(garis)
            except json.JSONDecodeError:
                continue
            if d.get("galat"):
                continue
            ada.add((d.get("label"), str(d.get("id"))))
    return ada


def _tulis_csv(jsonl, keluar):
    baris = []
    with open(jsonl, encoding="utf-8") as f:
        for garis in f:
            garis = garis.strip()
            if not garis:
                continue
            try:
                d = json.loads(garis)
            except json.JSONDecodeError:
                continue
            baris.append(d)
    terbaik = {}
    for d in baris:
        k = (d.get("label", ""), str(d.get("id", "")))
        lama = terbaik.get(k)
        if lama is None or (lama.get("galat") and not d.get("galat")):
            terbaik[k] = d
    baris = list(terbaik.values())
    baris.sort(key=lambda d: (d.get("label", ""), int(d.get("id", 0))))
    with open(keluar, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["label", "model", "id", "kode", "catatan", "kalimat_bukti",
                    "token_masuk", "token_keluar", "galat"])
        for d in baris:
            w.writerow([d.get("label", ""), d.get("model", ""), d.get("id", ""),
                        d.get("code", ""), d.get("note", ""),
                        d.get("evidence", ""), d.get("tok_in", ""),
                        d.get("tok_out", ""), d.get("galat", "")])
    return len(baris)


def jalankan(csv_sampel, berkas_prompt, jsonl=JSONL, batas=4000, lapor_tiap=25):
    if not uji_asap.MODEL:
        print("uji_asap.MODEL kosong.")
        return

    sistem = open(berkas_prompt, encoding="utf-8").read()
    with open(csv_sampel, newline="", encoding="utf-8") as f:
        baris = [b for b in csv.DictReader(f) if b.get("id")]

    ada = _sudah_ada(jsonl)
    print("Sampel        : %d baris" % len(baris))
    print("Sudah tersimpan: %d jawaban" % len(ada))
    print("Model         : %s\n" % ", ".join(m["label"] for m in uji_asap.MODEL))

    for cfg in uji_asap.MODEL:
        label = cfg["label"]
        sisa = [b for b in baris if (label, str(b["id"])) not in ada]
        print("=" * 62)
        print("%s  (%s)  —  %d dari %d baris perlu dipanggil"
              % (label, cfg["model"], len(sisa), len(baris)))
        print("=" * 62)
        if not sisa:
            print("  Sudah lengkap, dilewati.\n")
            continue

        t_awal = time.time()
        n_ok = n_gagal = 0
        with open(jsonl, "a", encoding="utf-8") as keluar:
            for i, b in enumerate(sisa, 1):
                teks = "id: %s\nblock_type: %s\n\npassage:\n%s" % (
                    b["id"], b.get("jenis", "prose"),
                    b.get("teks") or b.get("teks_paragraf", ""))
                rekam = {"label": label, "model": cfg["model"], "id": b["id"]}
                try:
                    jwb, mi, mo = uji_asap.panggil_ulang(cfg, sistem, teks, batas)
                    j = uji_asap.urai(jwb) or {}
                    rekam.update({"code": (j.get("code") or "").strip(),
                                  "note": (j.get("note") or "").strip(),
                                  "evidence": (j.get("evidence") or "").strip(),
                                  "id_jawab": j.get("id"),
                                  "tok_in": mi, "tok_out": mo})
                    salah = uji_asap.periksa(b["id"], j if j else None)
                    if salah:
                        rekam["periksa"] = "; ".join(salah)
                    n_ok += 1
                except Exception as e:
                    rekam["galat"] = str(e)[:300]
                    n_gagal += 1

                keluar.write(json.dumps(rekam, ensure_ascii=False) + "\n")
                keluar.flush()
                os.fsync(keluar.fileno())

                if i % lapor_tiap == 0 or i == len(sisa):
                    lewat = time.time() - t_awal
                    sisa_menit = (lewat / i) * (len(sisa) - i) / 60
                    print("  %4d/%d   berhasil %d  gagal %d   sisa ≈ %.0f menit"
                          % (i, len(sisa), n_ok, n_gagal, sisa_menit))

        print("  Selesai dalam %.0f menit.\n" % ((time.time() - t_awal) / 60))

    n = _tulis_csv(jsonl, CSV)
    print("=" * 62)
    print("%s ditulis — %d baris." % (CSV, n))


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print("Argumen tidak lengkap."); sys.exit(1)
    batas = int(sys.argv[3]) if len(sys.argv) == 4 else 4000
    jalankan(sys.argv[1], sys.argv[2], batas=batas)

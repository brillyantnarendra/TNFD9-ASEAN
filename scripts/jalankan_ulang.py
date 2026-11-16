import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import uji_asap
except ImportError:
    print("uji_asap.py tidak ditemukan.")
    sys.exit(1)

SAMPEL = "sampel.csv"
PROMPT = "prompt_pengodean.txt"

KONFIG = {
    "gpt": {"label": "openai", "gaya": "openai",
            "url": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-6-astra", "kunci": "OPENAI_API_KEY", "batas": 4000},
    "gemini": {"label": "gemini", "gaya": "openai",
               "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
               "model": "gemini-3.8-flash", "kunci": "GEMINI_API_KEY", "batas": 4000},
    "dsthink": {"label": "deepseek_think", "gaya": "openai",
                "url": "https://api.deepseek.com/chat/completions",
                "model": "deepseek-v4-pro", "kunci": "DEEPSEEK_API_KEY",
                "tambahan": {"thinking": {"type": "enabled"}},
                "varian": {"token": "max_tokens", "tanpa_suhu": True}, "batas": 16000},
    "ds": {"label": "deepseek", "gaya": "openai",
           "url": "https://api.deepseek.com/chat/completions",
           "model": "deepseek-v4-pro", "kunci": "DEEPSEEK_API_KEY",
           "tambahan": {"thinking": {"type": "disabled"}}, "batas": 4000},
    "cohere": {"label": "cohere", "gaya": "openai",
               "url": "https://api.cohere.ai/compatibility/v1/chat/completions",
               "model": "command-a-03-2025", "kunci": "COHERE_API_KEY",
               "jeda": 3.2, "batas": 4000},
}

TERAKHIR = {}
_post_asli = uji_asap.requests.post


def _post_rekam(*a, **k):
    r = _post_asli(*a, **k)
    TERAKHIR.clear()
    try:
        d = r.json()
        TERAKHIR["model_jawab"] = d.get("model")
        pakai = d.get("usage") or {}
        rinci = pakai.get("completion_tokens_details") or pakai.get("output_tokens_details") or {}
        TERAKHIR["tok_alasan"] = rinci.get("reasoning_tokens")
    except Exception:
        pass
    return r


uji_asap.requests.post = _post_rekam


def _kering(cfg, sistem, teks, batas):
    uid = teks.split("\n", 1)[0].replace("id:", "").strip()
    TERAKHIR.clear()
    TERAKHIR.update({"model_jawab": "KERING", "tok_alasan": None})
    return json.dumps({"id": uid, "code": "B1", "note": "", "evidence": "uji"}), 100, 10


def sudah_ada(path):
    ada = set()
    if not Path(path).exists():
        return ada
    with open(path, encoding="utf-8") as f:
        for g in f:
            try:
                d = json.loads(g)
            except json.JSONDecodeError:
                continue
            if not d.get("galat"):
                ada.add(str(d.get("id")))
    return ada


def tulis_csv(jsonl, keluar):
    terbaik = {}
    with open(jsonl, encoding="utf-8") as f:
        for g in f:
            try:
                d = json.loads(g)
            except json.JSONDecodeError:
                continue
            k = str(d.get("id"))
            if k not in terbaik or (terbaik[k].get("galat") and not d.get("galat")):
                terbaik[k] = d
    kol = ["label", "model", "model_jawab", "id", "code", "note", "evidence", "id_jawab",
           "tok_in", "tok_out", "tok_alasan", "detik", "waktu", "periksa", "galat"]
    with open(keluar, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(kol)
        for k in sorted(terbaik, key=lambda x: int(x)):
            w.writerow([terbaik[k].get(c, "") for c in kol])
    return len(terbaik), sum(1 for d in terbaik.values() if d.get("galat"))


def main():
    argv = sys.argv[1:]
    kering = "--kering" in argv
    n_uji = None
    if "--uji" in argv:
        i = argv.index("--uji")
        if i + 1 >= len(argv) or not argv[i + 1].isdigit():
            print("!! --uji harus diikuti jumlah unit, misalnya --uji 10")
            return
        n_uji = int(argv[i + 1])
        del argv[i:i + 2]
    arg = [a for a in argv if not a.startswith("--")]
    if len(arg) != 2 or arg[0] not in KONFIG or not arg[1].isdigit() or int(arg[1]) < 2:
        print("Argumen tidak lengkap.")
        return
    run, k = arg[0], int(arg[1])

    cfg = dict(KONFIG[run])
    batas = cfg.pop("batas")
    varian = cfg.pop("varian", None)
    cfg["label"] = "%s_r%d" % (cfg["label"], k)
    if varian:
        uji_asap.VARIAN[cfg["label"]] = dict(varian)
    if not kering and not os.environ.get(cfg["kunci"]):
        print("!! %s belum diisi. Contoh:  $env:%s = \"kunci-api\"" % (cfg["kunci"], cfg["kunci"]))
        return

    sistem = open(PROMPT, encoding="utf-8").read()
    with open(SAMPEL, newline="", encoding="utf-8-sig") as f:
        baris = [b for b in csv.DictReader(f) if b.get("id")]
    if n_uji:
        baris = uji_asap.pilih_baris(baris, n_uji)
        dasar = "Uji_%s%s" % (run, "_kering" if kering else "")
    else:
        dasar = "Ulang_%s_r%d%s" % (run, k, "_kering" if kering else "")
    jsonl, keluar = dasar + ".jsonl", dasar + ".csv"

    ada = sudah_ada(jsonl)
    sisa = [b for b in baris if str(b["id"]) not in ada]
    print("Run %s ulangan %d | model %s | label %s" % (run, k, cfg["model"], cfg["label"]))
    print("Prompt %s | sampel %d unit | sudah ada %d | perlu dipanggil %d | berkas %s"
          % (PROMPT, len(baris), len(ada), len(sisa), jsonl))
    if kering:
        print("MODE KERING: tidak ada panggilan API.")

    t0 = time.time()
    ok = gagal = 0
    out_tok = []
    with open(jsonl, "a", encoding="utf-8") as fo:
        for i, b in enumerate(sisa, 1):
            teks = "id: %s\nblock_type: %s\n\npassage:\n%s" % (
                b["id"], b.get("jenis", "prose"), b.get("teks") or b.get("teks_paragraf", ""))
            rek = {"label": cfg["label"], "model": cfg["model"], "id": b["id"],
                   "waktu": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            t1 = time.time()
            try:
                if kering:
                    jwb, mi, mo = _kering(cfg, sistem, teks, batas)
                else:
                    jwb, mi, mo = uji_asap.panggil_ulang(cfg, sistem, teks, batas)
                j = uji_asap.urai(jwb) or {}
                rek.update({"code": (j.get("code") or "").strip(),
                            "note": (j.get("note") or "").strip(),
                            "evidence": (j.get("evidence") or "").strip(),
                            "id_jawab": j.get("id"), "tok_in": mi, "tok_out": mo,
                            "model_jawab": TERAKHIR.get("model_jawab"),
                            "tok_alasan": TERAKHIR.get("tok_alasan")})
                salah = uji_asap.periksa(b["id"], j if j else None)
                if salah:
                    rek["periksa"] = "; ".join(salah)
                ok += 1
                if mo:
                    out_tok.append(int(mo))
            except Exception as e:
                rek["galat"] = str(e)[:300]
                gagal += 1
            rek["detik"] = round(time.time() - t1, 2)
            fo.write(json.dumps(rek, ensure_ascii=False) + "\n")
            fo.flush()
            os.fsync(fo.fileno())
            if i % 25 == 0 or i == len(sisa):
                lewat = time.time() - t0
                print("  %4d/%d  berhasil %d  gagal %d  sisa ≈ %.0f menit"
                      % (i, len(sisa), ok, gagal, lewat / i * (len(sisa) - i) / 60))

    n, ng = tulis_csv(jsonl, keluar)
    print("\n%s ditulis: %d unit, %d masih galat." % (keluar, n, ng))
    if out_tok:
        out_tok.sort()
        print("Median token keluar panggilan ini: %d" % out_tok[len(out_tok) // 2])
        if run == "ds" and out_tok[len(out_tok) // 2] > 400:
            print("!! Median token keluar run tanpa thinking melebihi 400.")
    if ng:
        print("Ada galat.")


if __name__ == "__main__":
    main()

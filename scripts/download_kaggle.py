"""Download the six Kaggle datasets (K1-K6) into data/raw/<key>/.

Credentials, in order of preference (never printed):
  1. KAGGLE_API_TOKEN (or a `Kaggle=` KGAT_... token) in the environment / .env  -> Bearer auth
  2. KAGGLE_USERNAME + KAGGLE_KEY in the environment / .env                         -> basic auth
  3. ~/.kaggle/kaggle.json {username, key}                                          -> basic auth

Anything already downloaded (a non-empty data/raw/<key>/ with a .done marker) is skipped.
Usage:  python scripts/download_kaggle.py [K1 K2 ...] [--check]
"""
from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

DATASETS = {
    "K1": "asaniczka/upwork-job-postings-dataset-2024-50k-records",
    "K2": "asaniczka/all-jobs-on-upwork-200k-plus",
    "K3": "ahmedmyalo/upwork-freelance-jobs-60k",
    "K4": "asaniczka/freelance-contracts-dataset-1-3-million-entries",
    "K5": "sarveshchhetri/freelancer-success-earnings-and-churn-prediction",
    "K6": "adityammantri/trial-1",
}
URL = "https://www.kaggle.com/api/v1/datasets/download/{ref}"


def get_auth() -> tuple[str, object] | None:
    load_dotenv(ROOT / ".env")
    token = os.getenv("KAGGLE_API_TOKEN") or os.getenv("Kaggle") or os.getenv("KAGGLE")
    if token and token.strip().startswith("KGAT_"):
        return "bearer", token.strip()
    user, key = os.getenv("KAGGLE_USERNAME"), os.getenv("KAGGLE_KEY")
    if user and key:
        return "basic", (user, key)
    kj = Path.home() / ".kaggle" / "kaggle.json"
    if kj.exists():
        try:
            d = json.loads(kj.read_text())
            return "basic", (d["username"], d["key"])
        except Exception:
            pass
    if token:  # a non-KGAT token in KAGGLE_API_TOKEN; try bearer anyway
        return "bearer", token.strip()
    return None


def download(key: str, ref: str, auth) -> None:
    out = RAW / key.lower()
    marker = out / ".done"
    if marker.exists():
        print(f"[skip] {key} already in {out.relative_to(ROOT)}")
        return
    out.mkdir(parents=True, exist_ok=True)
    kind, cred = auth
    headers = {"User-Agent": "gigbid-data-pipeline/1.0"}
    kwargs: dict = {"headers": headers, "follow_redirects": True, "timeout": httpx.Timeout(60, read=600)}
    if kind == "bearer":
        headers["Authorization"] = f"Bearer {cred}"
    else:
        kwargs["auth"] = cred
    print(f"[get ] {key} {ref} ...", flush=True)
    buf = io.BytesIO()
    with httpx.stream("GET", URL.format(ref=ref), **kwargs) as r:
        if r.status_code != 200:
            raise RuntimeError(f"{key}: HTTP {r.status_code}")
        for chunk in r.iter_bytes(1 << 20):
            buf.write(chunk)
    buf.seek(0)
    if zipfile.is_zipfile(buf):
        with zipfile.ZipFile(buf) as z:
            for m in z.infolist():
                # guard against path traversal
                target = (out / m.filename).resolve()
                if not str(target).startswith(str(out.resolve())):
                    continue
                z.extract(m, out)
    else:
        (out / f"{ref.split('/')[-1]}.bin").write_bytes(buf.getvalue())
    marker.write_text(ref)
    files = [p.name for p in out.iterdir() if p.name != ".done"]
    print(f"[ok  ] {key}: {len(buf.getvalue())/1e6:.1f} MB -> {files}", flush=True)


def main(argv: list[str]) -> int:
    auth = get_auth()
    if "--check" in argv:
        print("kaggle credentials:", "present" if auth else "missing")
        return 0 if auth else 1
    if auth is None:
        print("No Kaggle credentials (KAGGLE_API_TOKEN, KAGGLE_USERNAME/KAGGLE_KEY or ~/.kaggle/kaggle.json).")
        return 1
    keys = [a.upper() for a in argv if not a.startswith("-")] or list(DATASETS)
    failed = []
    for k in keys:
        try:
            download(k, DATASETS[k], auth)
        except Exception as e:  # noqa: BLE001
            print(f"[fail] {k}: {e}")
            failed.append(k)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

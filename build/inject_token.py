#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inject_token.py  —  메신저 올인원 빌드 도구  v1.5.1
════════════════════════════════════════════════════════════════
빌드 전 실행하여:
  1. PAT 토큰을 XOR+Base64 로 난독화 → core/auto_updater.py 에 삽입
  2. AES-256 랜덤 키 생성 → core/auto_updater.py 에 삽입
  3. messenger_allInOne.py 를 AES-256-CBC 로 암호화 → .enc 파일 생성
  4. SHA-256 해시 계산 → build/version.json 에 자동 기록

사용법:
  python inject_token.py --pat "ghp_xxxxxxxxxxxx"

옵션:
  --pat   GitHub PAT 토큰 (repo 권한 필요)
  --src   암호화할 소스 파일 (기본: ../messenger_allInOne_v1.7.0.py)
  --out   출력 .enc 파일 경로 (기본: ../messenger_allInOne.enc)
  --ver   version.json 경로 (기본: ./version.json)

⚠ 이 스크립트의 출력물(.enc, 수정된 auto_updater.py)만 배포하세요.
  평문 PAT 와 AES 키는 절대 커밋하지 마세요.
════════════════════════════════════════════════════════════════
"""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path

# AES 암호화는 pycryptodome 필요: pip install pycryptodome
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


# ────────────────────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────────────────────
XOR_KEY      = b"MSG_SECURE_2026"       # auto_updater.py 와 동일해야 함
BUILD_DIR    = Path(__file__).parent
ROOT_DIR     = BUILD_DIR.parent
UPDATER_PATH = ROOT_DIR / "core" / "auto_updater.py"
VERSION_JSON = BUILD_DIR / "version.json"


# ────────────────────────────────────────────────────────────
# 헬퍼 함수
# ────────────────────────────────────────────────────────────
def xor_encode(data: bytes, key: bytes) -> str:
    """XOR + Base64 인코딩"""
    encoded = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return base64.b64encode(encoded).decode()


def aes_encrypt(data: bytes, key: bytes) -> bytes:
    """AES-256-CBC 암호화. IV 를 앞 16바이트에 붙여서 반환."""
    if not _HAS_CRYPTO:
        raise RuntimeError(
            "pycryptodome 가 설치되지 않았습니다.\n"
            "pip install pycryptodome 를 실행하세요."
        )
    iv = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ct = cipher.encrypt(pad(data, AES.block_size))
    return iv + ct


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ────────────────────────────────────────────────────────────
# 메인 작업
# ────────────────────────────────────────────────────────────
def inject_into_updater(pat_encoded: str, aes_key_encoded: str):
    """auto_updater.py 의 플레이스홀더를 실제 값으로 교체."""
    src = UPDATER_PATH.read_text("utf-8")

    # PAT 교체
    src, n_pat = re.subn(
        r'_TOKEN_ENCODED\s*=\s*"##ENCODED_TOKEN##"',
        f'_TOKEN_ENCODED = "{pat_encoded}"',
        src,
    )
    if n_pat == 0:
        # 이미 교체된 경우 재교체
        src = re.sub(
            r'_TOKEN_ENCODED\s*=\s*"[A-Za-z0-9+/=]+"',
            f'_TOKEN_ENCODED = "{pat_encoded}"',
            src,
        )

    # AES 키 교체
    src, n_aes = re.subn(
        r'_AES_KEY_ENCODED\s*=\s*"##AES_KEY##"',
        f'_AES_KEY_ENCODED = "{aes_key_encoded}"',
        src,
    )
    if n_aes == 0:
        src = re.sub(
            r'_AES_KEY_ENCODED\s*=\s*"[A-Za-z0-9+/=]+"',
            f'_AES_KEY_ENCODED = "{aes_key_encoded}"',
            src,
        )

    UPDATER_PATH.write_text(src, encoding="utf-8")
    print(f"  ✅ auto_updater.py 업데이트 완료 (PAT 난독화 + AES 키 삽입)")


def update_version_json(enc_sha256: str, version_path: Path = VERSION_JSON):
    """version.json 의 enc_sha256 필드 업데이트."""
    try:
        data = json.loads(version_path.read_text("utf-8"))
        data["enc_sha256"] = enc_sha256
        version_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  ✅ version.json SHA-256 기록: {enc_sha256[:16]}...")
    except Exception as e:
        print(f"  ⚠ version.json 업데이트 실패: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="메신저 올인원 빌드 도구 — PAT 난독화 + AES 암호화"
    )
    parser.add_argument("--pat",  required=True, help="GitHub PAT 토큰")
    parser.add_argument(
        "--src",
        default=str(ROOT_DIR / "messenger_allInOne_v1.7.0.py"),
        help="암호화할 소스 파일",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT_DIR / "messenger_allInOne.enc"),
        help="출력 .enc 파일 경로",
    )
    parser.add_argument(
        "--ver",
        default=str(VERSION_JSON),
        help="version.json 경로",
    )
    args = parser.parse_args()

    src_path = Path(args.src)
    out_path = Path(args.out)
    ver_path = Path(args.ver)

    print("\n── 메신저 올인원 inject_token.py ──────────────────────")
    print(f"  소스 파일 : {src_path}")
    print(f"  출력 .enc : {out_path}")

    # ── 1) PAT 난독화 ───────────────────────────────────────
    print("\n[1/4] PAT XOR+Base64 난독화...")
    pat_encoded = xor_encode(args.pat.encode(), XOR_KEY)
    print(f"  인코딩 결과: {pat_encoded[:20]}...")

    # ── 2) AES-256 랜덤 키 생성 ─────────────────────────────
    print("\n[2/4] AES-256 랜덤 키 생성...")
    if not _HAS_CRYPTO:
        print("  ⚠ pycryptodome 없음 — AES 암호화를 건너뜁니다.")
        print("     pip install pycryptodome 를 실행하세요.")
        aes_key      = b""
        aes_key_b64  = "##AES_KEY##"
    else:
        aes_key      = os.urandom(32)
        aes_key_b64  = base64.b64encode(aes_key).decode()
        print(f"  키 (앞 8바이트): {aes_key[:8].hex()}...")

    # ── 3) auto_updater.py 에 삽입 ──────────────────────────
    print("\n[3/4] core/auto_updater.py 에 값 삽입...")
    inject_into_updater(pat_encoded, aes_key_b64)

    # ── 4) 소스 → .enc 암호화 ───────────────────────────────
    print("\n[4/4] 소스 파일 AES-256-CBC 암호화...")
    if not src_path.exists():
        print(f"  ❌ 소스 파일 없음: {src_path}")
        sys.exit(1)

    src_bytes = src_path.read_bytes()

    if _HAS_CRYPTO and aes_key:
        enc_bytes = aes_encrypt(src_bytes, aes_key)
        out_path.write_bytes(enc_bytes)
        sha = sha256_file(out_path)
        print(f"  ✅ 암호화 완료: {out_path.name}  ({len(enc_bytes):,} bytes)")
        print(f"  SHA-256: {sha}")
        update_version_json(sha, ver_path)
    else:
        print("  ⚠ AES 없음 — .enc 없이 version.json 만 업데이트합니다.")

    print("\n──────────────────────────────────────────────────────")
    print("✅ 완료! 이제 build.bat 으로 PyInstaller 빌드를 실행하세요.")
    print(f"   배포 파일: {out_path.name}  +  version.json")
    print("   ⚠ PAT 평문은 절대 GitHub 에 올리지 마세요!\n")


if __name__ == "__main__":
    main()

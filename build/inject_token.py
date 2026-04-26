#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inject_token.py  —  메신저 올인원 빌드 보안 도구  v1.5.0
════════════════════════════════════════════════════════════════
사용법:
    python inject_token.py <GITHUB_PAT> <AES_KEY_HEX_or_auto>

기능:
  1) PAT 토큰   → XOR + Base64 난독화 → core/auto_updater.py 에 주입
  2) AES-256 키 → Base64 인코딩       → core/auto_updater.py 에 주입
  3) 소스 파일   → AES-256-CBC 암호화 → messenger_allInOne.enc 생성
  4) SHA-256 해시 계산               → version.json 에 자동 기록
  5) _injected_auto_updater.py 생성  → PyInstaller 번들용

실행 순서 (build.bat 이 자동 호출):
    1. inject_token.py 실행 → .enc 생성 + SHA-256 계산
    2. PyInstaller 실행     → EXE 생성 (PAT+AES 내장)
    3. EXE + .enc 배포

⚠ 주의:
  - PAT 는 GitHub Private Repo 읽기 권한 필요
  - AES 키는 32 bytes (64 hex 문자) 또는 "auto" (자동생성)
  - .env 파일이나 환경변수로 PAT 를 전달하는 것을 권장
════════════════════════════════════════════════════════════════
"""

import sys
import os
import json
import base64
import hashlib
import secrets
import shutil
from pathlib import Path


# ── 경로 설정 ──────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent   # 메신저올인원 루트
CORE_DIR   = BASE_DIR / "core"
BUILD_DIR  = BASE_DIR / "build"

SRC_FILE   = BASE_DIR / "messenger_allInOne_v1.6.2.py"   # 암호화할 소스
ENC_FILE   = BASE_DIR / "messenger_allInOne.enc"           # 출력 .enc
VER_FILE   = BUILD_DIR / "version.json"                    # SHA-256 기록

UPDATER_SRC = CORE_DIR / "auto_updater.py"
UPDATER_INJ = BASE_DIR / "_injected_auto_updater.py"       # PyInstaller 번들용

XOR_KEY = b"MSG_SECURE_2026"


# ════════════════════════════════════════════════════════════════
# 1) PAT 난독화
# ════════════════════════════════════════════════════════════════
def encode_pat(pat: str) -> str:
    """PAT → XOR + Base64 인코딩 문자열"""
    raw = pat.encode()
    key = XOR_KEY
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
    return base64.b64encode(xored).decode()


# ════════════════════════════════════════════════════════════════
# 2) AES-256 키 생성/인코딩
# ════════════════════════════════════════════════════════════════
def make_aes_key(hex_or_auto: str) -> tuple[bytes, str]:
    """
    hex_or_auto: "auto" 이면 32 bytes 랜덤 생성,
                 그 외에는 64자 hex 문자열로 해석.
    반환: (raw_bytes_32, base64_encoded_str)
    """
    if hex_or_auto.lower() == "auto":
        raw = secrets.token_bytes(32)
    else:
        raw = bytes.fromhex(hex_or_auto)
        if len(raw) != 32:
            raise ValueError(f"AES 키는 32 bytes (64 hex 문자) 이어야 합니다. 현재: {len(raw)} bytes")
    return raw, base64.b64encode(raw).decode()


# ════════════════════════════════════════════════════════════════
# 3) AES-256-CBC 암호화
# ════════════════════════════════════════════════════════════════
def encrypt_file(src_path: Path, aes_key: bytes) -> bytes:
    """
    소스 파일을 AES-256-CBC 로 암호화하여 bytes 반환.
    포맷: [16 bytes IV] + [암호화 데이터 (PKCS7 패딩)]
    """
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
    except ImportError:
        print("❌ pycryptodome 이 필요합니다: pip install pycryptodome")
        sys.exit(1)

    src = src_path.read_bytes()
    iv  = secrets.token_bytes(16)
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    ct = cipher.encrypt(pad(src, AES.block_size))
    return iv + ct


# ════════════════════════════════════════════════════════════════
# 4) SHA-256 해시 계산
# ════════════════════════════════════════════════════════════════
def sha256_file(path: Path) -> str:
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    return h


# ════════════════════════════════════════════════════════════════
# 5) auto_updater.py 에 토큰 주입
# ════════════════════════════════════════════════════════════════
def inject_into_updater(
    pat_encoded: str,
    aes_encoded: str,
    out_path: Path = None,
) -> None:
    """
    core/auto_updater.py 의 ##ENCODED_TOKEN## / ##AES_KEY## 를
    실제 인코딩된 값으로 교체하여 out_path 에 저장.
    out_path 기본값: _injected_auto_updater.py (PyInstaller 번들용)
    """
    if out_path is None:
        out_path = UPDATER_INJ

    src = UPDATER_SRC.read_text("utf-8")
    src = src.replace('"##ENCODED_TOKEN##"', f'"{pat_encoded}"')
    src = src.replace('"##AES_KEY##"',       f'"{aes_encoded}"')

    # 모듈명도 교체 (임포트 오류 방지)
    src = src.replace(
        "from auto_updater import",
        "from _injected_auto_updater import",
    )

    out_path.write_text(src, encoding="utf-8")
    print(f"  ✅ 주입된 updater 저장: {out_path.name}")


# ════════════════════════════════════════════════════════════════
# 6) version.json 업데이트
# ════════════════════════════════════════════════════════════════
def update_version_json(sha256: str) -> None:
    ver_data = {}
    if VER_FILE.exists():
        try:
            ver_data = json.loads(VER_FILE.read_text("utf-8"))
        except Exception:
            pass
    ver_data["enc_sha256"] = sha256
    VER_FILE.write_text(json.dumps(ver_data, ensure_ascii=False, indent=2), "utf-8")
    print(f"  ✅ version.json SHA-256 갱신: {sha256[:16]}...")


# ════════════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════════════
def main():
    if len(sys.argv) < 3:
        print(
            "사용법: python inject_token.py <GITHUB_PAT> <AES_KEY|auto>\n"
            "\n"
            "  GITHUB_PAT : GitHub Personal Access Token (repo 읽기 권한)\n"
            "  AES_KEY    : 64자 hex 문자열 (32 bytes) 또는 'auto' (자동 생성)\n"
            "\n"
            "예시:\n"
            "  python inject_token.py ghp_xxxx... auto\n"
            "  python inject_token.py ghp_xxxx... abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
        )
        sys.exit(1)

    pat       = sys.argv[1].strip()
    aes_input = sys.argv[2].strip()

    print("\n[1] PAT 난독화...")
    pat_encoded = encode_pat(pat)
    print(f"    인코딩 완료 ({len(pat_encoded)} chars)")

    print("[2] AES-256 키 준비...")
    aes_key, aes_encoded = make_aes_key(aes_input)
    print(f"    키 준비 완료  hex: {aes_key.hex()[:16]}...")

    print("[3] 소스 암호화 →", ENC_FILE.name, "...")
    if not SRC_FILE.exists():
        print(f"    ❌ 소스 파일 없음: {SRC_FILE}")
        sys.exit(1)
    enc_data = encrypt_file(SRC_FILE, aes_key)
    ENC_FILE.write_bytes(enc_data)
    print(f"    ✅ 암호화 완료: {len(enc_data):,} bytes")

    print("[4] SHA-256 계산...")
    sha256 = sha256_file(ENC_FILE)
    print(f"    SHA-256: {sha256}")

    print("[5] auto_updater.py 에 토큰 주입...")
    inject_into_updater(pat_encoded, aes_encoded)

    print("[6] version.json SHA-256 갱신...")
    update_version_json(sha256)

    print("\n✅ 빌드 준비 완료!")
    print(f"   {ENC_FILE}")
    print(f"   {UPDATER_INJ}")
    print(f"\n다음 단계: PyInstaller 로 EXE 빌드 후 EXE + .enc 함께 배포")

    # AES 키 출력 (auto 생성한 경우 기록해둘 것)
    if aes_input.lower() == "auto":
        print(f"\n⚠ 자동 생성된 AES 키 (반드시 저장하세요):")
        print(f"   {aes_key.hex()}")


if __name__ == "__main__":
    main()

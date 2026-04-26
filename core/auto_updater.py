#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_updater.py  v1.5.0  —  messenger_allInOne 전용
════════════════════════════════════════════════════════════════
Private GitHub 레포 버전 체크 & 암호화된 파일 자동 다운로드

보안 구조:
  ① PAT 토큰  : XOR + Base64 난독화 → EXE 내부에만 존재
  ② GitHub API: Bearer 인증 → Private 레포 접근
  ③ 업데이트 파일: messenger_allInOne.enc (AES-256-CBC 암호화)
  ④ 복호화 키  : EXE 내부에만 존재, 디스크에 저장 안 됨

변경 이력:
  v1.5.0 (2026-04-26) — messenger_allInOne 전용으로 적용
    · 기반: auto-update-template v1.5.0
    · 대상 파일: messenger_allInOne.enc
    · 레포: lcm67088-tech/messenger-allInOne2  브랜치: main
════════════════════════════════════════════════════════════════
"""

import urllib.request
import urllib.error
import urllib.parse
import json
import os
import sys
import shutil
import base64
import time
import hashlib
from pathlib import Path


# ════════════════════════════════════════════════════════════════
# ① GitHub 설정
# ════════════════════════════════════════════════════════════════
GITHUB_OWNER  = "lcm67088-tech"
GITHUB_REPO   = "messenger-allInOne2"
GITHUB_BRANCH = "main"

# ════════════════════════════════════════════════════════════════
# ② PAT 토큰 난독화 (XOR + Base64)
#    ⚠ 빌드 시 build.bat → inject_token.py 가 자동 교체
#    ⚠ 평문 PAT는 절대 이 파일에 저장하지 않음
# ════════════════════════════════════════════════════════════════
_TOKEN_XOR_KEY = b"MSG_SECURE_2026"
_TOKEN_ENCODED = "##ENCODED_TOKEN##"   # ← build.bat 이 실제 값으로 교체


def _decode_token() -> str:
    """난독화된 PAT 토큰 복원 (런타임 전용)"""
    try:
        raw = base64.b64decode(_TOKEN_ENCODED.encode())
        key = _TOKEN_XOR_KEY
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(raw)).decode()
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════════
# ③ AES-256 복호화 키
#    ⚠ 빌드 시 inject_token.py 가 자동 교체
# ════════════════════════════════════════════════════════════════
_AES_KEY_ENCODED = "##AES_KEY##"       # ← build.bat 이 실제 값으로 교체


def _decode_aes_key() -> bytes:
    """내장 AES 키 반환 (32 bytes). 유효하지 않으면 빈 bytes."""
    try:
        key = base64.b64decode(_AES_KEY_ENCODED.encode())
        if len(key) != 32:
            return b""
        return key
    except Exception:
        return b""


# ════════════════════════════════════════════════════════════════
# ④ 경로 설정
# ════════════════════════════════════════════════════════════════
def get_app_dir() -> Path:
    """EXE 위치 (frozen) 또는 스크립트 위치 반환"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent   # core/ 상위 = 프로젝트 루트


APP_DIR       = get_app_dir()
LOCAL_ENC     = APP_DIR / "messenger_allInOne.enc"
LOCAL_VERSION = APP_DIR / "local_version.json"
BACKUP_ENC    = APP_DIR / "messenger_allInOne.enc.bak"

# 네트워크 타임아웃
_CONNECT_TIMEOUT = 5    # 연결 타임아웃 (초)
_READ_TIMEOUT    = 30   # 읽기 타임아웃 (초)
_MAX_RETRIES     = 3    # 재시도 횟수


# ════════════════════════════════════════════════════════════════
# ⑤ AES-256-CBC 복호화
# ════════════════════════════════════════════════════════════════
def _aes_decrypt(data: bytes, key: bytes) -> bytes:
    """
    AES-256-CBC 복호화.
    형식: [ IV (16 bytes) ][ PKCS7 패딩된 암호문 ]
    pycryptodome 사용, 없으면 명확한 오류 메시지 출력.
    """
    try:
        from Crypto.Cipher import AES as _AES
        iv     = data[:16]
        ct     = data[16:]
        cipher = _AES.new(key, _AES.MODE_CBC, iv)
        pt     = cipher.decrypt(ct)
        pad    = pt[-1]
        if pad < 1 or pad > 16:
            raise ValueError(f"PKCS7 패딩 오류: pad={pad}")
        return pt[:-pad]
    except ImportError:
        raise ImportError(
            "pycryptodome 패키지 없음.\n"
            "해결: pip install pycryptodome"
        )


def decrypt_file(enc_data: bytes) -> bytes:
    """
    암호화된 .enc 바이트 → 원본 Python 소스코드 반환.
    AES 키가 없거나 복호화 실패 시 ValueError 발생.
    """
    key = _decode_aes_key()
    if not key:
        raise ValueError(
            "AES 키 없음.\n"
            "원인: 빌드 시 inject_token.py 실행이 누락되었습니다.\n"
            "해결: build.bat 으로 다시 빌드하세요."
        )
    return _aes_decrypt(enc_data, key)


# ════════════════════════════════════════════════════════════════
# ⑥ GitHub API 요청 헬퍼
# ════════════════════════════════════════════════════════════════
def _make_headers() -> dict:
    """GitHub API 요청 헤더 (Private 레포 인증 포함)"""
    token = _decode_token()
    h = {
        "User-Agent":  "MessengerAllInOne-Updater/1.5",
        "Accept":      "application/vnd.github.v3.raw",
        "X-App-Name":  "messenger-allInOne",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _api_url(filename: str) -> str:
    """GitHub Contents API URL 생성"""
    encoded = urllib.parse.quote(filename, safe="")
    return (
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/contents/{encoded}?ref={GITHUB_BRANCH}"
    )


def _fetch_text(url: str, retries: int = _MAX_RETRIES) -> str | None:
    """URL 에서 텍스트 가져오기 (재시도 포함). 실패 시 None 반환."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_make_headers())
            with urllib.request.urlopen(
                req,
                timeout=(_CONNECT_TIMEOUT + _READ_TIMEOUT)
            ) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                return None
        except (urllib.error.URLError, OSError):
            pass

        if attempt < retries - 1:
            time.sleep(2 ** attempt)

    return None


def _download_binary(
    url: str,
    dest: Path,
    progress_cb=None,
    retries: int = _MAX_RETRIES,
) -> bool:
    """URL → dest 이진 파일 다운로드 (재시도 포함)."""
    for attempt in range(retries):
        tmp = dest.with_suffix(".tmp")
        try:
            req = urllib.request.Request(url, headers=_make_headers())
            with urllib.request.urlopen(
                req,
                timeout=(_CONNECT_TIMEOUT + _READ_TIMEOUT)
            ) as resp:
                total      = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 8192

                with open(tmp, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb and total:
                            progress_cb(downloaded, total)

            if dest.exists():
                shutil.copy2(str(dest), str(BACKUP_ENC))
            shutil.move(str(tmp), str(dest))
            return True

        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                _cleanup_tmp(tmp)
                return False
        except Exception:
            pass

        _cleanup_tmp(tmp)
        if attempt < retries - 1:
            time.sleep(2 ** attempt)

    return False


def _cleanup_tmp(tmp: Path):
    try:
        if tmp.exists():
            tmp.unlink()
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════
# ⑦ SHA-256 무결성 검증
# ════════════════════════════════════════════════════════════════
def _verify_sha256(data: bytes, expected_hex: str) -> bool:
    if not expected_hex:
        return True
    actual = hashlib.sha256(data).hexdigest()
    return actual.lower() == expected_hex.lower()


# ════════════════════════════════════════════════════════════════
# ⑧ 버전 관리
# ════════════════════════════════════════════════════════════════
def _parse_ver(v: str) -> tuple:
    """버전 문자열 → 정수 튜플 ("1.6.2" → (1,6,2))"""
    try:
        return tuple(int(x) for x in str(v).strip().split("."))
    except Exception:
        return (0, 0, 0)


def is_newer(remote: str, local: str) -> bool:
    return _parse_ver(remote) > _parse_ver(local)


def load_local_version() -> dict:
    if LOCAL_VERSION.exists():
        try:
            with open(LOCAL_VERSION, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": "0.0.0", "update_note": ""}


def save_local_version(info: dict):
    try:
        with open(LOCAL_VERSION, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════
# ⑨ UpdateInfo
# ════════════════════════════════════════════════════════════════
class UpdateInfo:
    def __init__(self):
        self.available    : bool  = False
        self.remote_ver   : str   = ""
        self.local_ver    : str   = ""
        self.update_note  : str   = ""
        self.release_date : str   = ""
        self.force_update : bool  = False
        self.enc_sha256   : str   = ""
        self.online       : bool  = False
        self.error        : str   = ""

    def __repr__(self):
        return (
            f"<UpdateInfo online={self.online} available={self.available} "
            f"local={self.local_ver} remote={self.remote_ver} force={self.force_update}>"
        )


# ════════════════════════════════════════════════════════════════
# ⑩ 메인 API
# ════════════════════════════════════════════════════════════════
def check_update() -> UpdateInfo:
    """GitHub 에서 version.json 을 읽어 업데이트 여부 확인."""
    result           = UpdateInfo()
    local_info       = load_local_version()
    result.local_ver = local_info.get("version", "0.0.0")

    raw = _fetch_text(_api_url("version.json"))
    if raw is None:
        result.online = False
        result.error  = (
            "GitHub 에 연결할 수 없습니다.\n"
            "(오프라인 상태이거나 PAT 토큰이 올바르지 않습니다.)"
        )
        return result

    try:
        remote_info = json.loads(raw)
    except json.JSONDecodeError as e:
        result.online = False
        result.error  = f"version.json 파싱 오류: {e}"
        return result

    result.online        = True
    result.remote_ver    = remote_info.get("version",      "0.0.0")
    result.update_note   = remote_info.get("update_note",  "")
    result.release_date  = remote_info.get("release_date", "")
    result.force_update  = bool(remote_info.get("force_update", False))
    result.enc_sha256    = remote_info.get("enc_sha256",   "")
    result.available     = is_newer(result.remote_ver, result.local_ver)
    return result


def apply_update(progress_cb=None) -> tuple[bool, str]:
    """messenger_allInOne.enc 를 GitHub 에서 다운로드하고 교체."""
    sha256_expected = ""
    raw_ver = _fetch_text(_api_url("version.json"))
    if raw_ver:
        try:
            sha256_expected = json.loads(raw_ver).get("enc_sha256", "")
        except Exception:
            pass

    ok = _download_binary(
        _api_url("messenger_allInOne.enc"),
        LOCAL_ENC,
        progress_cb=progress_cb,
    )

    if not ok:
        if BACKUP_ENC.exists():
            shutil.copy2(str(BACKUP_ENC), str(LOCAL_ENC))
        return False, "다운로드 실패 – 이전 버전으로 복구되었습니다."

    if sha256_expected:
        try:
            actual_data = LOCAL_ENC.read_bytes()
            if not _verify_sha256(actual_data, sha256_expected):
                if BACKUP_ENC.exists():
                    shutil.copy2(str(BACKUP_ENC), str(LOCAL_ENC))
                else:
                    LOCAL_ENC.unlink(missing_ok=True)
                return False, "SHA-256 무결성 검증 실패 – 이전 버전으로 복구되었습니다."
        except Exception:
            pass

    if raw_ver:
        try:
            save_local_version(json.loads(raw_ver))
        except Exception:
            pass

    return True, "업데이트 완료"


def rollback() -> bool:
    """백업(.bak) 에서 현재 .enc 파일을 복구."""
    if BACKUP_ENC.exists():
        try:
            shutil.copy2(str(BACKUP_ENC), str(LOCAL_ENC))
            return True
        except Exception:
            pass
    return False

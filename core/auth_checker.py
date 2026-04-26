#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth_checker.py  —  메신저 올인원 전용 인증 모듈  v1.5.1
────────────────────────────────────────────────────────────
Google Sheets CSV export URL 에서 허용 계정 목록을 실시간으로 불러와
ID / PW / EXPIRE / STATUS 를 검증.

▸ config.json 의 "sheet_url" 키 → 없으면 코드 상수 SHEET_URL 사용
▸ urllib 전용 (requests 의존 없음)
▸ AuthResult Enum 기반 명확한 인증 결과 분류

스프레드시트 컬럼 구조:
    ID | PW | EXPIRE (YYYY-MM-DD) | STATUS (ACTIVE/INACTIVE)

변경 이력:
  v1.5.1 (2026-04-26) — 메신저 올인원 전용 적용
    · set_sheet_url() 추가 → config.json 연동 (런타임 URL 교체)
    · User-Agent 를 MessengerAllInOne-Auth 로 변경
    · SHEET_URL 기본값 → 메신저 올인원 시트
  v1.5.0 (2026-04-26) — 기반 템플릿 (auto-update-template v1.5.0)
────────────────────────────────────────────────────────────
"""

import urllib.request
import urllib.error
import csv
import io
import json
from pathlib import Path
from datetime import date, datetime
from dataclasses import dataclass
from enum import Enum


# ══════════════════════════════════════════════════════════
# 구글 스프레드시트 기본 설정
#   · config.json 의 "sheet_url" 로 런타임에 덮어쓸 수 있음
# ══════════════════════════════════════════════════════════
_SHEET_URL_DEFAULT = (
    "https://docs.google.com/spreadsheets/d/"
    "17FeZ6QSDjfVJanOly36jsGPaImZCMzol7bM8HvnUuRA"
    "/export?format=csv&gid=0"
)

# 모듈 내부 활성 URL (set_sheet_url() 로 교체 가능)
_active_sheet_url: str = _SHEET_URL_DEFAULT

TIMEOUT = 8   # 네트워크 타임아웃(초)


def set_sheet_url(url: str) -> None:
    """런타임에 시트 URL 을 교체한다 (config.json 연동용)."""
    global _active_sheet_url
    if url and url.startswith("http"):
        _active_sheet_url = url


def get_sheet_url() -> str:
    """현재 활성화된 시트 URL 반환."""
    return _active_sheet_url


def load_sheet_url_from_config(config_path: str | Path | None = None) -> str:
    """
    config.json 에서 sheet_url 을 읽어 모듈 URL 을 갱신한 뒤 반환.
    파일이 없거나 키가 없으면 기본값 유지.
    """
    if config_path is None:
        # 기본 위치: 실행파일 옆 Config/config.json
        config_path = Path(__file__).parent.parent / "Config" / "config.json"

    try:
        cfg = json.loads(Path(config_path).read_text("utf-8"))
        url = cfg.get("sheet_url", "")
        if url:
            set_sheet_url(url)
    except Exception:
        pass
    return _active_sheet_url


# ══════════════════════════════════════════════════════════
# 인증 결과 타입
# ══════════════════════════════════════════════════════════
class AuthResult(Enum):
    OK            = "ok"
    WRONG_ID_PW   = "wrong_id_pw"      # ID 또는 PW 불일치
    EXPIRED       = "expired"           # 유효기간 만료
    INACTIVE      = "inactive"          # STATUS = INACTIVE
    OFFLINE       = "offline"           # 네트워크 연결 불가
    SHEET_ERROR   = "sheet_error"       # 시트 파싱 오류


@dataclass
class AuthInfo:
    result:   AuthResult
    message:  str = ""
    user_id:  str = ""
    expire:   str = ""          # 만료일 (표시용)


# ══════════════════════════════════════════════════════════
# 스프레드시트 로드
# ══════════════════════════════════════════════════════════
def _fetch_sheet_csv(timeout: int = TIMEOUT) -> str | None:
    """구글 시트 CSV 텍스트 반환. 실패 시 None"""
    try:
        req = urllib.request.Request(
            _active_sheet_url,
            headers={"User-Agent": "MessengerAllInOne-Auth/1.5.1"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return None


def _parse_accounts(csv_text: str) -> list[dict]:
    """
    CSV → 계정 딕셔너리 리스트 변환
    반환: [{"id": ..., "pw": ..., "expire": ..., "status": ...}, ...]
    """
    accounts = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        # 컬럼명 대소문자 무관하게 처리 / 한글 헤더도 허용
        normalized = {k.strip().upper(): v.strip() for k, v in row.items()}
        acc = {
            "id":     normalized.get("ID", ""),
            "pw":     normalized.get("PW", ""),
            "expire": normalized.get("EXPIRE", ""),
            "status": normalized.get("STATUS", "ACTIVE").upper(),
        }
        if acc["id"]:   # ID 없는 빈 행 제외
            accounts.append(acc)
    return accounts


# ══════════════════════════════════════════════════════════
# 인증 로직
# ══════════════════════════════════════════════════════════
def _check_expire(expire_str: str) -> bool:
    """
    만료일 검사.
    EXPIRE 컬럼이 비어있으면 무기한 허용.
    반환: True = 아직 유효, False = 만료됨
    """
    if not expire_str:
        return True
    try:
        expire_date = datetime.strptime(expire_str, "%Y-%m-%d").date()
        return date.today() <= expire_date
    except ValueError:
        return True   # 날짜 형식 오류 → 허용 (관대하게 처리)


def verify(user_id: str, password: str) -> AuthInfo:
    """
    메인 인증 함수.
    입력: 사용자가 입력한 ID / PW
    반환: AuthInfo 객체

    ※ 호출 전에 set_sheet_url() 또는 load_sheet_url_from_config() 로
      시트 URL 을 설정해야 실제 인증 서버가 적용됩니다.
    """
    user_id  = user_id.strip()
    password = password.strip()

    # ── 시트 로드 ────────────────────────────────────
    csv_text = _fetch_sheet_csv()
    if csv_text is None:
        return AuthInfo(
            result  = AuthResult.OFFLINE,
            message = "서버에 연결할 수 없습니다.\n인터넷 연결을 확인하세요.",
        )

    # ── 파싱 ─────────────────────────────────────────
    try:
        accounts = _parse_accounts(csv_text)
    except Exception as e:
        return AuthInfo(
            result  = AuthResult.SHEET_ERROR,
            message = f"인증 데이터 오류: {e}",
        )

    if not accounts:
        return AuthInfo(
            result  = AuthResult.SHEET_ERROR,
            message = "허용 계정 목록이 비어 있습니다.",
        )

    # ── ID 검색 ───────────────────────────────────────
    matched = None
    for acc in accounts:
        if acc["id"].lower() == user_id.lower():
            matched = acc
            break

    if matched is None:
        return AuthInfo(
            result  = AuthResult.WRONG_ID_PW,
            message = "아이디 또는 비밀번호가 올바르지 않습니다.",
        )

    # ── PW 검사 (대소문자 구분) ───────────────────────
    if matched["pw"] != password:
        return AuthInfo(
            result  = AuthResult.WRONG_ID_PW,
            message = "아이디 또는 비밀번호가 올바르지 않습니다.",
        )

    # ── STATUS 검사 ───────────────────────────────────
    if matched["status"] not in ("ACTIVE", "활성", "1", "TRUE", "YES", ""):
        return AuthInfo(
            result  = AuthResult.INACTIVE,
            message = (
                f"계정이 비활성화되었습니다. (STATUS={matched['status']})\n"
                "관리자에게 문의하세요."
            ),
            user_id = matched["id"],
        )

    # ── 만료일 검사 ───────────────────────────────────
    if not _check_expire(matched["expire"]):
        return AuthInfo(
            result  = AuthResult.EXPIRED,
            message = (
                f"사용 기간이 만료되었습니다. (만료일: {matched['expire']})\n"
                "관리자에게 문의하세요."
            ),
            user_id = matched["id"],
            expire  = matched["expire"],
        )

    # ── 인증 성공 ─────────────────────────────────────
    return AuthInfo(
        result  = AuthResult.OK,
        message = "로그인 성공",
        user_id = matched["id"],
        expire  = matched["expire"],
    )

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_online.py — 온라인/오프라인 원인 진단 도구
실행: python build\check_online.py
"""
import sys
import json
import urllib.request
import urllib.error
import base64

sys.path.insert(0, "core")
import auto_updater

print("=" * 55)
print("  메신저올인원 온라인 진단 도구")
print("=" * 55)

# 1) 토큰 확인
token = auto_updater._decode_token()
if token:
    print(f"\n[1] PAT 토큰: ✅ ({token[:15]}...)")
else:
    print("\n[1] PAT 토큰: ❌ 없음 — inject_token.py 다시 실행 필요")
    sys.exit(1)

# 2) 실제 API 요청 테스트 (상세 오류 출력)
url = auto_updater._api_url("version.json")
print(f"\n[2] 요청 URL: {url}")

headers = auto_updater._make_headers()
print(f"[3] Authorization 헤더: Bearer {token[:15]}...")

try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        data = json.loads(body)
        print(f"\n[4] 응답: ✅ 성공!")
        print(f"    버전: {data.get('version')}")
        print(f"    날짜: {data.get('release_date')}")
        print("\n결론: 온라인 정상 — EXE 재빌드 후 다시 실행하세요.")
except urllib.error.HTTPError as e:
    print(f"\n[4] HTTP 오류: {e.code} {e.reason}")
    if e.code == 401:
        print("    → PAT 권한 없음 또는 만료됨")
    elif e.code == 403:
        print("    → 접근 거부 (레포 권한 확인)")
    elif e.code == 404:
        print("    → 파일 또는 레포 경로 없음")
    body = e.read().decode("utf-8", errors="replace")
    print(f"    응답 내용: {body[:300]}")
except urllib.error.URLError as e:
    print(f"\n[4] 네트워크 오류: {e.reason}")
    print("    → 인터넷 연결 확인")
except Exception as e:
    print(f"\n[4] 알 수 없는 오류: {e}")

print("=" * 55)

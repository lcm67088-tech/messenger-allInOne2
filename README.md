# 메신저 올인원 (messenger_allInOne)

> 카카오톡·텔레그램 자동화 올인원 도구 — v1.7.0

---

## 버전 히스토리

| 버전 | 날짜 | 주요 변경 |
|------|------|-----------|
| **v1.7.0** | 2026-04-26 | 자동업데이트 풀시스템 통합 (4단계 보안) |
| v1.6.2 | 2026-04-26 | UI 클립보드 옵션 제거 / Semantic Versioning 적용 |
| v1.6.1 | 2026-04-26 | 클립보드 완전 제거 / SendInput 직접 입력 |

---

## v1.7.0 신규 기능

### 4단계 보안 레이어
```
[1] Google Sheets 로그인   — ID/PW/만료일/STATUS 실시간 검증 (5회 실패 시 종료)
[2] Private GitHub 레포   — PAT XOR+Base64 난독화 → EXE 내부에만 존재
[3] AES-256-CBC 암호화    — .enc 파일, 디스크에 평문 없음
[4] 메모리 실행           — 복호화 후 exec(), 파일로 쓰지 않음
```

### 실행 흐름
```
EXE 실행
  └─ [1] 로그인 창 (Google Sheets 인증)
       └─ 인증 성공
            └─ [2] 스플래시 창 표시
                 └─ [3] 백그라운드 GitHub 버전 체크
                      ├─ 최신 버전 → 앱 바로 실행
                      ├─ 새 버전 발견 → 업데이트 팝업
                      │    ├─ [지금 업데이트] → .enc 다운로드 → 앱 실행
                      │    └─ [나중에] → 현재 버전으로 실행
                      └─ 오프라인 → 현재 버전으로 실행
```

---

## 프로젝트 구조

```
messenger-allInOne2/
├── messenger_allInOne_v1.7.0.py   ← 메인 파일 (런처 통합)
│
├── core/                          ← 런처 보안 모듈
│   ├── __init__.py
│   ├── auto_updater.py            ← GitHub 버전체크 + AES 다운로드
│   ├── auth_checker.py            ← Google Sheets 인증 (urllib 전용)
│   └── login_window.py            ← 로그인 GUI
│
├── build/                         ← 빌드 도구
│   ├── build.bat                  ← PyInstaller 원클릭 빌드
│   ├── inject_token.py            ← PAT 난독화 + AES 암호화 도구
│   └── version.json               ← 배포 버전 정보 (GitHub 업로드용)
│
└── Config/                        ← 런타임 설정 (사용자 PC에 위치)
    ├── config.json                ← sheet_url 등 설정
    └── templates/                 ← 자동화 템플릿
```

---

## 빌드 방법 (EXE 배포)

### 사전 준비
```bash
pip install pyinstaller pycryptodome
```

### 빌드 순서
```
1. GitHub PAT 발급 (repo 권한 필요)
   → https://github.com/settings/tokens

2. build/inject_token.py 실행 (PAT 난독화 + AES 암호화)
   python build/inject_token.py --pat "ghp_xxxxxxxxxxxx"
   → core/auto_updater.py 에 PAT/AES 키 삽입
   → messenger_allInOne.enc 생성
   → build/version.json SHA-256 자동 기록

3. build/build.bat 실행 (원클릭 빌드)
   → PAT 입력 프롬프트 → inject_token.py 자동 실행 → PyInstaller 빌드

4. GitHub 배포
   - dist/messenger_allInOne.enc → GitHub 레포에 업로드
   - build/version.json → GitHub 레포에 업로드 (version.json으로)
   ⚠ .exe는 최초 1회만 배포, 이후는 .enc + version.json만 업데이트
```

---

## 업데이트 배포 방법 (EXE 재배포 없음)

```
1. 소스 수정 후 inject_token.py 실행
   → 새 .enc 생성 + version.json SHA-256/버전 갱신

2. GitHub에 새 .enc 와 version.json 업로드
   → 사용자가 다음 실행 시 자동으로 업데이트 팝업 표시
```

---

## core/ 모듈 설명

### `core/auto_updater.py`
- GitHub API Bearer 인증 (Private 레포 접근)
- PAT 토큰 XOR+Base64 난독화 (`_TOKEN_ENCODED`)
- AES-256-CBC 복호화 키 내장 (`_AES_KEY_ENCODED`)
- 재시도 3회, 지수 백오프, 연결/읽기 타임아웃 분리
- SHA-256 무결성 검증 + 롤백 지원

### `core/auth_checker.py`
- Google Sheets CSV export 실시간 인증
- `set_sheet_url()` / `load_sheet_url_from_config()` 로 런타임 URL 교체
- AuthResult Enum: OK / WRONG_ID_PW / EXPIRED / INACTIVE / OFFLINE / SHEET_ERROR
- urllib 전용 (requests 의존 없음)

### `core/login_window.py`
- 메신저 올인원 전용 로그인 GUI (Tkinter)
- `config_path` 인수로 Config/config.json 의 `sheet_url` 자동 연동
- 최대 5회 실패 시 프로그램 종료

---

## Google Sheets 계정 관리

스프레드시트 컬럼 구조:
```
| ID | PW | EXPIRE (YYYY-MM-DD) | STATUS (ACTIVE/INACTIVE) |
```

- `STATUS = INACTIVE` → 즉시 차단 (EXE 재배포 불필요)
- `EXPIRE` 날짜 지나면 자동 차단
- `config.json` 의 `sheet_url` 키로 시트 URL 변경 가능

---

## GitHub 레포

- **Repository**: https://github.com/lcm67088-tech/messenger-allInOne2
- **Branch**: main
- **주요 파일**:
  - `messenger_allInOne.enc` — 배포용 암호화 실행 파일
  - `version.json` — 버전 정보 (자동업데이트 트리거)

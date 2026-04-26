#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
login_window.py  —  메신저 올인원 로그인 GUI  v1.5.1
────────────────────────────────────────────────────────────
구글 스프레드시트 기반 ID/PW 인증 창.
인증 성공 시 True, 실패/취소 시 False 반환.

▸ config_path 인수로 config.json 경로 전달 → sheet_url 자동 연동
▸ auth_checker.py (urllib 전용) 사용 — requests 의존 없음
▸ 최대 5회 실패 시 강제 종료

변경 이력:
  v1.5.1 (2026-04-26) — 메신저 올인원 전용 적용
    · 타이틀/아이콘을 메신저 올인원으로 커스터마이징
    · config_path 인수 지원 (sheet_url 자동 로드)
    · 메신저 올인원 PALETTE 색상과 동일 톤 적용
  v1.5.0 (2026-04-26) — 기반 템플릿 (auto-update-template v1.5.0)
────────────────────────────────────────────────────────────
"""

import tkinter as tk
import tkinter.ttk as ttk
import threading
import sys
import os
from pathlib import Path

# auth_checker 임포트 (core/ 패키지로 설치되어 있음)
try:
    from core.auth_checker import (
        verify, AuthResult,
        load_sheet_url_from_config, set_sheet_url,
    )
    _AUTH_OK = True
except ImportError:
    try:
        # core/ 폴더를 sys.path에 추가 후 재시도
        _core_dir = str(Path(__file__).parent.resolve())
        if _core_dir not in sys.path:
            sys.path.insert(0, _core_dir)
        from auth_checker import (
            verify, AuthResult,
            load_sheet_url_from_config, set_sheet_url,
        )
        _AUTH_OK = True
    except ImportError:
        _AUTH_OK = False


# ── 색상 팔레트 (메신저 올인원 PALETTE 와 동일 톤) ──────────
C = {
    "bg":       "#1a1a2e",
    "card":     "#0f3460",
    "accent":   "#e94560",
    "accent2":  "#533483",
    "green":    "#4ecca3",
    "yellow":   "#f5a623",
    "text":     "#eaeaea",
    "sub":      "#a8a8b3",
    "input_bg": "#16213e",
    "border":   "#533483",
}

MAX_ATTEMPTS = 5   # 최대 로그인 시도 횟수


class LoginWindow(tk.Tk):
    """
    메신저 올인원 로그인 창.
    .run() 을 호출하면 인증 결과(bool)를 반환.

    Parameters
    ----------
    config_path : str | Path | None
        Config/config.json 경로.
        전달하면 sheet_url 을 읽어 인증 URL 을 자동 교체.
    """

    def __init__(self, config_path=None):
        super().__init__()
        self.title("메신저 올인원 — 로그인")
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self._result   = False
        self._attempts = 0
        self._locked   = False

        W, H = 420, 500
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        # config.json 에서 sheet_url 로드
        if _AUTH_OK and config_path is not None:
            try:
                load_sheet_url_from_config(config_path)
            except Exception:
                pass

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ──────────────────────────────────────────
    # UI 구성
    # ──────────────────────────────────────────
    def _build_ui(self):
        # 상단 액센트 바
        tk.Frame(self, bg=C["accent"], height=4).pack(fill="x")

        body = tk.Frame(self, bg=C["bg"], padx=44)
        body.pack(fill="both", expand=True)

        # 아이콘 + 타이틀
        tk.Label(body,
            text="✉",
            font=("Segoe UI Emoji", 38),
            bg=C["bg"], fg=C["accent"],
        ).pack(pady=(28, 2))

        tk.Label(body,
            text="메신저 올인원",
            font=("Malgun Gothic", 15, "bold"),
            bg=C["bg"], fg=C["text"],
        ).pack()

        tk.Label(body,
            text="허가된 사용자만 이용할 수 있습니다",
            font=("Malgun Gothic", 9),
            bg=C["bg"], fg=C["sub"],
        ).pack(pady=(2, 18))

        # 구분선
        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=(0, 18))

        # ── 아이디 입력 ────────────────────────────────────
        tk.Label(body,
            text="아이디",
            font=("Malgun Gothic", 9, "bold"),
            bg=C["bg"], fg=C["sub"],
            anchor="w",
        ).pack(fill="x")

        self._id_var = tk.StringVar()
        id_frame = tk.Frame(body, bg=C["border"], pady=1, padx=1)
        id_frame.pack(fill="x", pady=(3, 12))
        self._id_entry = tk.Entry(id_frame,
            textvariable=self._id_var,
            font=("Malgun Gothic", 11),
            bg=C["input_bg"], fg=C["text"],
            insertbackground=C["text"],
            relief="flat", bd=7,
        )
        self._id_entry.pack(fill="x")

        # ── 비밀번호 입력 ──────────────────────────────────
        tk.Label(body,
            text="비밀번호",
            font=("Malgun Gothic", 9, "bold"),
            bg=C["bg"], fg=C["sub"],
            anchor="w",
        ).pack(fill="x")

        self._pw_var = tk.StringVar()
        pw_frame = tk.Frame(body, bg=C["border"], pady=1, padx=1)
        pw_frame.pack(fill="x", pady=(3, 6))
        self._pw_entry = tk.Entry(pw_frame,
            textvariable=self._pw_var,
            font=("Malgun Gothic", 11),
            bg=C["input_bg"], fg=C["text"],
            insertbackground=C["text"],
            relief="flat", bd=7, show="●",
        )
        self._pw_entry.pack(fill="x")

        # 엔터키 바인딩
        self._id_entry.bind("<Return>", lambda e: self._pw_entry.focus())
        self._pw_entry.bind("<Return>", lambda e: self._on_login())

        # ── 상태 메시지 ────────────────────────────────────
        self._msg_var = tk.StringVar(value="")
        self._msg_lbl = tk.Label(body,
            textvariable=self._msg_var,
            font=("Malgun Gothic", 9),
            bg=C["bg"], fg=C["accent"],
            wraplength=300, justify="center",
        )
        self._msg_lbl.pack(pady=(10, 0))

        # ── 로그인 버튼 ────────────────────────────────────
        self._login_btn = tk.Button(body,
            text="로그인",
            command=self._on_login,
            bg=C["accent"], fg="#ffffff",
            font=("Malgun Gothic", 11, "bold"),
            relief="flat", cursor="hand2",
            pady=10, activebackground="#c73652",
        )
        self._login_btn.pack(fill="x", pady=(14, 0))

        # 로딩 프로그레스바 (기본 숨김)
        self._progress = ttk.Progressbar(body, mode="indeterminate", length=330)

        # ── 하단 안내 ──────────────────────────────────────
        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=(22, 10))
        tk.Label(body,
            text="계정 문의: 관리자에게 연락하세요",
            font=("Malgun Gothic", 8),
            bg=C["bg"], fg=C["sub"],
        ).pack()

        # 포커스
        self._id_entry.focus()

    # ──────────────────────────────────────────
    # 로그인 처리
    # ──────────────────────────────────────────
    def _on_login(self):
        if self._locked:
            return

        user_id  = self._id_var.get().strip()
        password = self._pw_var.get().strip()

        if not user_id or not password:
            self._set_msg("아이디와 비밀번호를 모두 입력하세요.", C["yellow"])
            return

        # UI 잠금 + 로딩 표시
        self._locked = True
        self._login_btn.config(state="disabled", text="확인 중...")
        self._set_msg("인증 서버에 연결 중...", C["yellow"])
        self._progress.pack(pady=(8, 0))
        self._progress.start(10)
        self.update()

        # auth_checker 없으면 임시 통과 (개발 모드)
        if not _AUTH_OK:
            self.after(500, lambda: self._on_verify_done(
                _FallbackAuthInfo(user_id)
            ))
            return

        # 백그라운드에서 인증
        def do_verify():
            info = verify(user_id, password)
            self.after(0, lambda: self._on_verify_done(info))

        threading.Thread(target=do_verify, daemon=True).start()

    def _on_verify_done(self, info):
        # 로딩 해제
        self._progress.stop()
        self._progress.pack_forget()
        self._locked = False
        self._login_btn.config(state="normal", text="로그인")

        # auth_checker 없는 경우 fallback
        if not _AUTH_OK:
            self._set_msg("✅ 로그인 성공! (개발 모드)", C["green"])
            self.update()
            self._result = True
            self.after(700, self.destroy)
            return

        result = getattr(info, "result", None)

        if result == AuthResult.OK:
            # 성공
            expire_txt = f" (만료일: {info.expire})" if getattr(info, "expire", "") else ""
            self._set_msg(f"✅ 로그인 성공!{expire_txt}", C["green"])
            self.update()
            self._result = True
            self.after(700, self.destroy)

        elif result == AuthResult.OFFLINE:
            self._set_msg(
                "⚠️ 인터넷 연결을 확인하세요.\n인증 서버에 접속할 수 없습니다.",
                C["yellow"],
            )
            self._attempts += 1
            self._check_lockout()

        elif result == AuthResult.WRONG_ID_PW:
            self._attempts += 1
            remain = MAX_ATTEMPTS - self._attempts
            if remain > 0:
                self._set_msg(
                    f"❌ {info.message}\n(남은 시도: {remain}회)",
                    C["accent"],
                )
            self._pw_var.set("")
            self._pw_entry.focus()
            self._check_lockout()

        else:
            # EXPIRED / INACTIVE / SHEET_ERROR
            self._set_msg(f"🚫 {info.message}", C["accent"])
            self._attempts += 1
            self._pw_var.set("")
            self._check_lockout()

    def _check_lockout(self):
        """최대 시도 초과 시 창 닫기"""
        if self._attempts >= MAX_ATTEMPTS:
            self._set_msg(
                f"❌ 로그인 {MAX_ATTEMPTS}회 실패.\n프로그램을 종료합니다.",
                C["accent"],
            )
            self.update()
            self.after(2000, self.destroy)

    def _set_msg(self, text: str, color: str = None):
        self._msg_var.set(text)
        if color:
            self._msg_lbl.config(fg=color)
        self.update_idletasks()

    def _on_close(self):
        """X 버튼 클릭 → 인증 실패 처리"""
        self._result = False
        self.destroy()

    # ──────────────────────────────────────────
    # 외부 호출 진입점
    # ──────────────────────────────────────────
    def run(self) -> bool:
        """
        로그인 창 실행.
        반환: True = 인증 성공, False = 실패/취소
        """
        self.mainloop()
        return self._result


# ──────────────────────────────────────────────
# auth_checker 없을 때 사용할 Fallback 객체
# ──────────────────────────────────────────────
class _FallbackAuthInfo:
    """auth_checker 임포트 실패 시 임시 성공 반환용."""
    def __init__(self, uid: str):
        self.result  = None    # AuthResult.OK 와 구분되도록 None
        self.message = "개발 모드 (auth_checker 없음)"
        self.user_id = uid
        self.expire  = ""


# ──────────────────────────────────────────────
# 단독 테스트
# ──────────────────────────────────────────────
if __name__ == "__main__":
    win = LoginWindow()
    ok  = win.run()
    print("인증 결과:", "성공" if ok else "실패/취소")

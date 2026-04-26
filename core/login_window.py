#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
login_window.py  —  메신저 올인원 전용 로그인 GUI  v1.5.1
────────────────────────────────────────────────────────────
auth_checker.verify() 를 백그라운드 스레드로 호출하여
인증 결과를 반환한다.

  · LoginWindow().run() → True (성공) / False (실패/취소)
  · 최대 5회 실패 시 강제 종료
  · 엔터키 지원, 비밀번호 마스킹
  · requests 의존 없음 (urllib 전용)

변경 이력:
  v1.5.1 (2026-04-26) — 메신저 올인원 전용
    · 아이콘 ✉ → 메신저 올인원 UI 톤으로 변경
    · auth_checker.load_sheet_url_from_config() 로 시트 URL 자동 연동
    · APP_TITLE 동적 연동 (messenger 모듈 상수 없어도 fallback)
────────────────────────────────────────────────────────────
"""

import tkinter as tk
import tkinter.ttk as ttk
import threading

from auth_checker import verify, AuthResult, load_sheet_url_from_config

# 색상 팔레트 (messenger_allInOne 기존 PALETTE 와 통일)
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


def _get_app_title() -> str:
    """APP_VERSION 상수가 있으면 사용, 없으면 기본값."""
    try:
        import importlib, sys
        # 메인 모듈이 이미 로드된 경우 버전 가져오기
        for name, mod in sys.modules.items():
            v = getattr(mod, "APP_VERSION", None)
            if v and isinstance(v, str) and v.startswith("1."):
                return f"메신저 올인원 v{v}"
    except Exception:
        pass
    return "메신저 올인원"


class LoginWindow(tk.Tk):
    """
    로그인 창.
    .run() 을 호출하면 인증 결과(bool)를 반환.
    """

    def __init__(self, config_path=None):
        super().__init__()

        # config.json 에서 sheet_url 로드
        load_sheet_url_from_config(config_path)

        self.title(f"{_get_app_title()} — 로그인")
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

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ──────────────────────────────────────────
    # UI 구성
    # ──────────────────────────────────────────
    def _build_ui(self):
        # 상단 강조 바
        tk.Frame(self, bg=C["accent"], height=4).pack(fill="x")

        body = tk.Frame(self, bg=C["bg"], padx=44)
        body.pack(fill="both", expand=True)

        # 아이콘 + 타이틀
        tk.Label(body, text="✉",
            font=("Segoe UI Emoji", 38),
            bg=C["bg"], fg=C["accent"],
        ).pack(pady=(28, 4))

        tk.Label(body, text=_get_app_title(),
            font=("Malgun Gothic", 14, "bold"),
            bg=C["bg"], fg=C["text"],
        ).pack()

        tk.Label(body, text="허가된 사용자만 이용할 수 있습니다",
            font=("Malgun Gothic", 9),
            bg=C["bg"], fg=C["sub"],
        ).pack(pady=(2, 18))

        # 구분선
        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=(0, 18))

        # ID 입력
        tk.Label(body, text="아이디",
            font=("Malgun Gothic", 9, "bold"),
            bg=C["bg"], fg=C["sub"], anchor="w",
        ).pack(fill="x")

        self._id_var = tk.StringVar()
        id_frame = tk.Frame(body, bg=C["border"], pady=1, padx=1)
        id_frame.pack(fill="x", pady=(3, 12))
        self._id_entry = tk.Entry(id_frame,
            textvariable=self._id_var,
            font=("Malgun Gothic", 11),
            bg=C["input_bg"], fg=C["text"],
            insertbackground=C["text"],
            relief="flat", bd=6,
        )
        self._id_entry.pack(fill="x")

        # PW 입력
        tk.Label(body, text="비밀번호",
            font=("Malgun Gothic", 9, "bold"),
            bg=C["bg"], fg=C["sub"], anchor="w",
        ).pack(fill="x")

        self._pw_var = tk.StringVar()
        pw_frame = tk.Frame(body, bg=C["border"], pady=1, padx=1)
        pw_frame.pack(fill="x", pady=(3, 6))
        self._pw_entry = tk.Entry(pw_frame,
            textvariable=self._pw_var,
            font=("Malgun Gothic", 11),
            bg=C["input_bg"], fg=C["text"],
            insertbackground=C["text"],
            relief="flat", bd=6, show="●",
        )
        self._pw_entry.pack(fill="x")

        # 엔터키 바인딩
        self._id_entry.bind("<Return>", lambda e: self._pw_entry.focus())
        self._pw_entry.bind("<Return>", lambda e: self._on_login())

        # 상태 메시지
        self._msg_var = tk.StringVar(value="")
        self._msg_lbl = tk.Label(body,
            textvariable=self._msg_var,
            font=("Malgun Gothic", 9),
            bg=C["bg"], fg=C["accent"],
            wraplength=320, justify="center",
        )
        self._msg_lbl.pack(pady=(10, 0))

        # 로그인 버튼
        self._login_btn = tk.Button(body,
            text="로그인",
            command=self._on_login,
            bg=C["accent"], fg="#ffffff",
            font=("Malgun Gothic", 11, "bold"),
            relief="flat", cursor="hand2",
            pady=10, activebackground="#c73652",
        )
        self._login_btn.pack(fill="x", pady=(12, 0))

        # 로딩 프로그레스바 (처음엔 숨김)
        self._progress = ttk.Progressbar(body, mode="indeterminate", length=332)

        # 하단 안내
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

        if info.result == AuthResult.OK:
            expire_str = f"  (만료: {info.expire})" if info.expire else ""
            self._set_msg(f"✅ 로그인 성공! ({info.user_id}){expire_str}", C["green"])
            self.update()
            self._result = True
            self.after(700, self.destroy)

        elif info.result == AuthResult.OFFLINE:
            self._set_msg(
                "⚠️ 인터넷 연결을 확인하세요.\n인증 서버에 접속할 수 없습니다.",
                C["yellow"],
            )
            self._attempts += 1
            self._check_lockout()

        elif info.result == AuthResult.WRONG_ID_PW:
            self._attempts += 1
            remain = MAX_ATTEMPTS - self._attempts
            msg = f"❌ {info.message}"
            if remain > 0:
                msg += f"\n(남은 시도: {remain}회)"
            self._set_msg(msg, C["accent"])
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
        """최대 시도 초과 시 창 닫기."""
        if self._attempts >= MAX_ATTEMPTS:
            self._set_msg(
                f"❌ 로그인 {MAX_ATTEMPTS}회 실패.\n프로그램을 종료합니다.",
                C["accent"],
            )
            self.update()
            self.after(2000, self.destroy)

    def _set_msg(self, text: str, color: str | None = None):
        self._msg_var.set(text)
        if color:
            self._msg_lbl.config(fg=color)
        self.update_idletasks()

    def _on_close(self):
        """X 버튼 클릭 → 인증 실패 처리."""
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
# 단독 테스트
# ──────────────────────────────────────────────
if __name__ == "__main__":
    win = LoginWindow()
    ok  = win.run()
    print("인증 결과:", "성공" if ok else "실패/취소")

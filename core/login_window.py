#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
login_window.py  —  메신저 올인원 로그인 GUI  v1.7.0
────────────────────────────────────────────────────────────
v1.7.0 (2026-04-26)
  · 카드형 레이아웃으로 완전 재설계
  · 다크 테마 PALETTE 메인앱과 완전 동일 통일
  · 폰트 Malgun Gothic 10pt 기준 통일 (8/11/13pt 혼재 제거)
  · pack 단일 방향 사용 - grid 혼용 제거 (정렬 깨짐 해소)
  · 이모지 아이콘 폰트 28pt → 22pt 조정
  · 입력창 포커스 하이라이트 효과 추가
  · 비밀번호 보기/숨기기 토글 추가
  · 로그인 버튼 hover 효과 추가
"""

import tkinter as tk
import tkinter.ttk as ttk
import threading
import sys
from pathlib import Path

try:
    from core.auth_checker import (
        verify, AuthResult,
        load_sheet_url_from_config, set_sheet_url,
    )
    _AUTH_OK = True
except ImportError:
    try:
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

# ── 색상 팔레트 (메인앱 PALETTE 완전 동일) ──────────────────────
C = {
    "bg":       "#1E1E2E",   # 메인 배경
    "sidebar":  "#161622",   # 헤더 배경 (더 깊은 다크)
    "card":     "#2A2A3E",   # 카드/패널
    "card2":    "#242438",   # 입력창 배경
    "border":   "#383850",   # 일반 테두리
    "border2":  "#4A4A65",   # 강조 테두리 (포커스)
    "primary":  "#5C7CFA",   # 블루 포인트
    "primary2": "#4568F5",   # 블루 호버
    "success":  "#51CF66",   # 성공 초록
    "danger":   "#FF6B6B",   # 위험 레드
    "warning":  "#FFD43B",   # 경고 황색
    "text":     "#E8E8F0",   # 기본 텍스트
    "text2":    "#A0A0B8",   # 보조 텍스트
    "muted":    "#6E6E88",   # 힌트 텍스트
}

# ── 폰트 (Malgun Gothic 10pt 기준 통일) ──────────────────────────
_FF      = "Malgun Gothic"
F_TITLE  = (_FF, 13, "bold")   # 앱 타이틀
F_LABEL  = (_FF, 10, "bold")   # 입력창 레이블
F_INPUT  = (_FF, 10)           # 입력창 텍스트
F_BTN    = (_FF, 10, "bold")   # 버튼
F_MSG    = (_FF, 10)           # 상태 메시지
F_SMALL  = (_FF,  9)           # 하단 안내
F_ICON   = ("Segoe UI Emoji", 22)  # 아이콘 이모지

MAX_ATTEMPTS = 5


class LoginWindow(tk.Tk):
    def __init__(self, config_path=None):
        super().__init__()
        self.title("메신저 올인원")
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self._result   = False
        self._attempts = 0
        self._locked   = False
        self._pw_visible = False

        # 창 크기 & 화면 중앙 배치
        W, H = 400, 500
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

        # config.json sheet_url 연동
        if _AUTH_OK and config_path is not None:
            try:
                load_sheet_url_from_config(config_path)
            except Exception:
                pass

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ──────────────────────────────────────────────────────────────
    # UI 구성
    # ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ① 상단 포인트 바 (3px)
        tk.Frame(self, bg=C["primary"], height=3).pack(fill="x", side="top")

        # ② 헤더 영역
        self._build_header()

        # ③ 구분선
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")

        # ④ 폼 카드 영역
        self._build_form()

        # ⑤ 하단 안내
        self._build_footer()

    def _build_header(self):
        hdr = tk.Frame(self, bg=C["sidebar"], pady=20)
        hdr.pack(fill="x")

        # 아이콘 + 타이틀을 수직 정렬로 중앙에 표시
        tk.Label(
            hdr,
            text="✉",
            font=F_ICON,
            bg=C["sidebar"],
            fg=C["primary"],
        ).pack()

        tk.Label(
            hdr,
            text="메신저 올인원",
            font=F_TITLE,
            bg=C["sidebar"],
            fg=C["text"],
        ).pack(pady=(6, 3))

        tk.Label(
            hdr,
            text="허가된 사용자만 이용 가능합니다",
            font=F_SMALL,
            bg=C["sidebar"],
            fg=C["muted"],
        ).pack()

    def _build_form(self):
        body = tk.Frame(self, bg=C["bg"], padx=36, pady=24)
        body.pack(fill="both", expand=True)

        # ── 아이디 입력 ──────────────────────────────────────────
        tk.Label(
            body,
            text="아이디",
            font=F_LABEL,
            bg=C["bg"],
            fg=C["text2"],
            anchor="w",
        ).pack(fill="x", pady=(0, 5))

        id_frame = tk.Frame(body, bg=C["border"], pady=1, padx=1)
        id_frame.pack(fill="x", pady=(0, 16))

        id_inner = tk.Frame(id_frame, bg=C["card2"])
        id_inner.pack(fill="x")

        self._id_var = tk.StringVar()
        self._id_entry = tk.Entry(
            id_inner,
            textvariable=self._id_var,
            font=F_INPUT,
            bg=C["card2"],
            fg=C["text"],
            insertbackground=C["primary"],
            relief="flat",
            bd=8,
        )
        self._id_entry.pack(fill="x")

        # ── 비밀번호 입력 ────────────────────────────────────────
        tk.Label(
            body,
            text="비밀번호",
            font=F_LABEL,
            bg=C["bg"],
            fg=C["text2"],
            anchor="w",
        ).pack(fill="x", pady=(0, 5))

        pw_frame = tk.Frame(body, bg=C["border"], pady=1, padx=1)
        pw_frame.pack(fill="x", pady=(0, 6))

        pw_inner = tk.Frame(pw_frame, bg=C["card2"])
        pw_inner.pack(fill="x")

        self._pw_var = tk.StringVar()
        self._pw_entry = tk.Entry(
            pw_inner,
            textvariable=self._pw_var,
            font=F_INPUT,
            bg=C["card2"],
            fg=C["text"],
            insertbackground=C["primary"],
            relief="flat",
            bd=8,
            show="●",
        )
        self._pw_entry.pack(side="left", fill="x", expand=True)

        # 비밀번호 보기 토글 버튼
        self._eye_btn = tk.Button(
            pw_inner,
            text="👁",
            font=("Segoe UI Emoji", 10),
            bg=C["card2"],
            fg=C["muted"],
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=6,
            command=self._toggle_pw,
            activebackground=C["card2"],
            activeforeground=C["text2"],
        )
        self._eye_btn.pack(side="right")

        # 포커스 하이라이트 효과
        self._id_entry.bind("<FocusIn>",  lambda e: id_frame.config(bg=C["primary"]))
        self._id_entry.bind("<FocusOut>", lambda e: id_frame.config(bg=C["border"]))
        self._pw_entry.bind("<FocusIn>",  lambda e: pw_frame.config(bg=C["primary"]))
        self._pw_entry.bind("<FocusOut>", lambda e: pw_frame.config(bg=C["border"]))

        # 엔터키 바인딩
        self._id_entry.bind("<Return>", lambda e: self._pw_entry.focus())
        self._pw_entry.bind("<Return>", lambda e: self._on_login())

        # ── 상태 메시지 ─────────────────────────────────────────
        self._msg_var = tk.StringVar(value="")
        self._msg_lbl = tk.Label(
            body,
            textvariable=self._msg_var,
            font=F_MSG,
            bg=C["bg"],
            fg=C["danger"],
            wraplength=310,
            justify="center",
            anchor="center",
        )
        self._msg_lbl.pack(pady=(10, 0), fill="x")

        # ── 로그인 버튼 ─────────────────────────────────────────
        self._login_btn = tk.Button(
            body,
            text="로그인",
            command=self._on_login,
            bg=C["primary"],
            fg=C["text"],
            font=F_BTN,
            relief="flat",
            cursor="hand2",
            pady=10,
            activebackground=C["primary2"],
            activeforeground=C["text"],
        )
        self._login_btn.pack(fill="x", pady=(16, 0))

        # 버튼 hover 효과
        self._login_btn.bind("<Enter>", lambda e: self._login_btn.config(bg=C["primary2"]))
        self._login_btn.bind("<Leave>", lambda e: self._login_btn.config(bg=C["primary"]))

        # ── 진행 바 (로그인 중) ──────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Login.Horizontal.TProgressbar",
            troughcolor=C["card"],
            background=C["primary"],
            bordercolor=C["border"],
            lightcolor=C["primary"],
            darkcolor=C["primary"],
        )
        self._progress = ttk.Progressbar(
            body,
            mode="indeterminate",
            style="Login.Horizontal.TProgressbar",
        )
        # 처음엔 숨겨둠 (로그인 클릭 시 pack)

        self._id_entry.focus()

    def _build_footer(self):
        foot = tk.Frame(self, bg=C["sidebar"], pady=10)
        foot.pack(fill="x", side="bottom")

        tk.Frame(foot, bg=C["border"], height=1).pack(fill="x", pady=(0, 8))
        tk.Label(
            foot,
            text="계정 문의: 관리자에게 연락하세요",
            font=F_SMALL,
            bg=C["sidebar"],
            fg=C["muted"],
        ).pack()

    # ──────────────────────────────────────────────────────────────
    # 이벤트 핸들러
    # ──────────────────────────────────────────────────────────────
    def _toggle_pw(self):
        self._pw_visible = not self._pw_visible
        self._pw_entry.config(show="" if self._pw_visible else "●")
        self._eye_btn.config(fg=C["primary"] if self._pw_visible else C["muted"])

    def _on_login(self):
        if self._locked:
            return
        uid = self._id_var.get().strip()
        pw  = self._pw_var.get().strip()

        if not uid or not pw:
            self._set_msg("아이디와 비밀번호를 모두 입력하세요.", C["warning"])
            return

        self._locked = True
        self._login_btn.config(state="disabled", text="확인 중...")
        self._set_msg("인증 서버에 연결 중...", C["text2"])
        self._progress.pack(fill="x", pady=(10, 0))
        self._progress.start(12)
        self.update()

        if not _AUTH_OK:
            # 개발 모드: 0.6초 후 바로 성공 처리
            self.after(600, lambda: self._on_verify_done(_FallbackAuth(uid)))
            return

        def do_verify():
            info = verify(uid, pw)
            self.after(0, lambda: self._on_verify_done(info))

        threading.Thread(target=do_verify, daemon=True).start()

    def _on_verify_done(self, info):
        self._progress.stop()
        self._progress.pack_forget()
        self._locked = False
        self._login_btn.config(state="normal", text="로그인")

        if not _AUTH_OK:
            self._set_msg("✅ 로그인 성공 (개발 모드)", C["success"])
            self._result = True
            self.after(600, self.destroy)
            return

        result = getattr(info, "result", None)

        if result == AuthResult.OK:
            exp = f"  (만료: {info.expire})" if getattr(info, "expire", "") else ""
            self._set_msg(f"✅ 로그인 성공{exp}", C["success"])
            self._result = True
            self.after(700, self.destroy)

        elif result == AuthResult.OFFLINE:
            self._set_msg("⚠ 인터넷 연결을 확인하세요.", C["warning"])
            self._attempts += 1
            self._check_lockout()

        elif result == AuthResult.WRONG_ID_PW:
            self._attempts += 1
            remain = MAX_ATTEMPTS - self._attempts
            msg = "❌ 아이디 또는 비밀번호 오류"
            if remain > 0:
                msg += f"  (남은 시도: {remain}회)"
            self._set_msg(msg, C["danger"])
            self._pw_var.set("")
            self._pw_entry.focus()
            self._check_lockout()

        else:
            self._set_msg(f"🚫 {info.message}", C["danger"])
            self._attempts += 1
            self._pw_var.set("")
            self._check_lockout()

    def _check_lockout(self):
        if self._attempts >= MAX_ATTEMPTS:
            self._set_msg(
                f"❌ {MAX_ATTEMPTS}회 실패 — 프로그램을 종료합니다.",
                C["danger"],
            )
            self.update()
            self.after(2000, self.destroy)

    def _set_msg(self, text: str, color: str = None):
        self._msg_var.set(text)
        if color:
            self._msg_lbl.config(fg=color)
        self.update_idletasks()

    def _on_close(self):
        self._result = False
        self.destroy()

    def run(self) -> bool:
        self.mainloop()
        return self._result


# ── 개발 모드용 폴백 인증 객체 ────────────────────────────────────
class _FallbackAuth:
    def __init__(self, uid):
        self.result  = None
        self.message = "개발 모드"
        self.user_id = uid
        self.expire  = ""


if __name__ == "__main__":
    win = LoginWindow()
    print("결과:", "성공" if win.run() else "실패")

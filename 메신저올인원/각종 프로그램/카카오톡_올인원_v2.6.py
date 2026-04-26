
# ============================================================
# 헤더/imports/경로헬퍼
# ============================================================

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
카카오톡 플로팅 자동화 v2.6
단일 파일 버전

변경사항 (v2.5 → v2.6):
  - 자동반복 기능 제거
  - 메시지 계정 치환({{id}}/{{pw}}) 제거
  - 프리셋/Config 폴더 구조 정상화
    · 실행 파일 옆 Config/ 폴더에 config.json 저장
    · 프리셋 개별 파일은 Config/presets/ 폴더에 저장
  - 닫기 방식에 ESC 추가
  - 도움말 창 추가
  - 전반적인 가독성 개선
"""

import os
import sys
import json
import time
import random
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

import pyautogui
import keyboard
import requests
import csv
from io import StringIO

# ──────────────────────────────────────────────
# pyautogui 안전 설정
# ──────────────────────────────────────────────
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.0

# ──────────────────────────────────────────────
# 구글 시트 URL (로그인 인증용)
# ──────────────────────────────────────────────
SHEET_URL = "https://docs.google.com/spreadsheets/d/17FeZ6QSDjfVJanOly36jsGPaImZCMzol7bM8HvnUuRA/export?format=csv&gid=0"

# ──────────────────────────────────────────────
# 경로 헬퍼
# ──────────────────────────────────────────────
def get_base_path():
    """실행 파일(또는 스크립트) 기준 디렉토리"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_config_dir():
    """Config 폴더 경로 — 없으면 자동 생성"""
    d = os.path.join(get_base_path(), "Config")
    os.makedirs(d, exist_ok=True)
    return d

def get_preset_dir():
    """Config/presets 폴더 경로 — 없으면 자동 생성"""
    d = os.path.join(get_config_dir(), "presets")
    os.makedirs(d, exist_ok=True)
    return d

def get_config_path():
    """메인 설정 파일 경로"""
    return os.path.join(get_config_dir(), "config.json")



# ============================================================
# safe_int/safe_float/calculate_coords/LoginDialog/StopController/type_msg/drag
# ============================================================

def safe_int(s, default=0):
    try:
        return int(str(s).strip())
    except Exception:
        return default

def safe_float(s, default=0.0):
    try:
        return float(str(s).strip())
    except Exception:
        return default

def sanitize_name(name):
    """프리셋 파일명용 안전 문자열 변환"""
    return re.sub(r"[^0-9A-Za-z가-힣_-]", "_", name.strip()).strip("_") or "preset"


def calculate_coordinates(start_x, start_y, cell_height,
                           column_count, row_count, column_gap,
                           scan_dir="col"):
    """
    그리드 좌표 자동 계산
    scan_dir="col" : 열 우선 (↓→) — col0의 row0~N → col1의 row0~N → ...
    scan_dir="row" : 행 우선 (→↓) — row0의 col0~N → row1의 col0~N → ...
    x = start_x + col * column_gap
    y = start_y + row * cell_height
    """
    coords = []
    if scan_dir == "col":
        for col in range(column_count):
            for row in range(row_count):
                x = start_x + col * column_gap
                y = start_y + row * cell_height
                coords.append((round(x), round(y)))
    else:
        for row in range(row_count):
            for col in range(column_count):
                x = start_x + col * column_gap
                y = start_y + row * cell_height
                coords.append((round(x), round(y)))
    return coords


def filter_valid_coords(coords):
    """화면 밖 좌표 필터링 (음수 허용 → 듀얼 모니터 고려)"""
    try:
        sw, sh = pyautogui.size()
    except Exception:
        sw, sh = 1920 * 3, 1080 * 3   # 넉넉하게 잡음
    valid = [(x, y) for x, y in coords if -sw < x < sw * 2 and -sh < y < sh * 2]
    return valid


# ══════════════════════════════════════════════
# CHUNK 03 — LoginDialog (구글 시트 인증)
# ══════════════════════════════════════════════

class LoginDialog:
    """구글 시트 CSV 기반 로그인"""

    def __init__(self, sheet_url=None, debug=False):
        self.sheet_url   = sheet_url or SHEET_URL
        self.debug       = debug
        self.authenticated = False
        self.username    = None

        self.root = tk.Tk()
        self.root.title("카카오톡 플로팅 자동화 v2.6 — 로그인")
        self.root.geometry("440x320")
        self.root.resizable(False, False)
        self.root.configure(bg=THEME["bg"])
        self._center()
        self._build()

    def _center(self):
        self.root.update_idletasks()
        w, h = 440, 320
        x = (self.root.winfo_screenwidth()  - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        outer = tk.Frame(self.root, bg=THEME["bg"])
        outer.pack(expand=True, fill="both", padx=32, pady=24)

        # 제목
        tk.Label(outer, text="🚀  카카오톡 플로팅 자동화", font=("Segoe UI Semibold", 14),
                 bg=THEME["bg"], fg=THEME["text_primary"]).pack(pady=(0, 4))
        tk.Label(outer, text="v2.5", font=("Segoe UI", 10),
                 bg=THEME["bg"], fg=THEME["text_muted"]).pack(pady=(0, 20))

        # ID 행
        row_id = tk.Frame(outer, bg=THEME["bg"])
        row_id.pack(fill="x", pady=5)
        tk.Label(row_id, text="ID", width=5, anchor="w",
                 font=("Segoe UI", 10), bg=THEME["bg"], fg=THEME["text_muted"]).pack(side="left")
        self.id_var = tk.StringVar()
        tk.Entry(row_id, textvariable=self.id_var, font=("Segoe UI", 10),
                 bg=THEME["card"], relief="solid", bd=1, width=28).pack(side="left", padx=(4,0))

        # PW 행
        row_pw = tk.Frame(outer, bg=THEME["bg"])
        row_pw.pack(fill="x", pady=5)
        tk.Label(row_pw, text="PW", width=5, anchor="w",
                 font=("Segoe UI", 10), bg=THEME["bg"], fg=THEME["text_muted"]).pack(side="left")
        self.pw_var = tk.StringVar()
        tk.Entry(row_pw, textvariable=self.pw_var, show="●", font=("Segoe UI", 10),
                 bg=THEME["card"], relief="solid", bd=1, width=28).pack(side="left", padx=(4,0))

        # 버튼 행
        row_btn = tk.Frame(outer, bg=THEME["bg"])
        row_btn.pack(pady=20)
        tk.Button(row_btn, text="  로그인  ", command=self._login,
                  font=("Segoe UI Semibold", 10), bg=THEME["accent"], fg="white",
                  relief="flat", padx=16, pady=6, cursor="hand2").pack(side="left", padx=6)
        tk.Button(row_btn, text="  종료  ", command=self._exit,
                  font=("Segoe UI", 10), bg=THEME["border"], fg=THEME["text_muted"],
                  relief="flat", padx=16, pady=6, cursor="hand2").pack(side="left", padx=6)

        tk.Label(outer, text="※ 관리자에게 ID/PW 문의", font=("Segoe UI", 9),
                 bg=THEME["bg"], fg=THEME["text_muted"]).pack(pady=(4, 0))

        # 단축키
        self.id_var  # focus
        self.root.bind("<Return>", lambda e: self._login())
        self.root.after(100, lambda: self.root.focus_force())

    def _load_users(self):
        try:
            resp = requests.get(self.sheet_url, timeout=10)
            resp.raise_for_status()
            reader = csv.DictReader(StringIO(resp.text))
            users = {}
            for row in reader:
                uid  = (row.get("ID") or row.get("id") or "").strip()
                pw   = (row.get("PASSWORD") or row.get("password") or
                        row.get("PW") or row.get("pw") or "").strip()
                exp  = (row.get("EXPIRE") or row.get("expire") or
                        row.get("만료일") or "").strip()
                stat = (row.get("STATUS") or row.get("status") or
                        row.get("활성여부") or row.get("상태") or "").strip()
                if uid:
                    users[uid] = {"pw": pw, "expire": exp, "status": stat}
            return users
        except requests.RequestException as e:
            messagebox.showerror("연결 오류", f"구글 시트 연결 실패:\n{e}")
            return None
        except Exception as e:
            messagebox.showerror("오류", str(e))
            return None

    def _check_expire(self, exp_str):
        if not exp_str:
            return True
        try:
            return datetime.now() <= datetime.strptime(exp_str, "%Y-%m-%d")
        except Exception:
            return True

    def _login(self):
        uid = self.id_var.get().strip()
        pw  = self.pw_var.get().strip()
        if not uid or not pw:
            messagebox.showwarning("입력 필요", "ID와 PW를 입력하세요.")
            return

        users = self._load_users()
        if users is None:
            return

        info = users.get(uid)
        if not info or info["pw"] != pw:
            messagebox.showerror("로그인 실패", "ID 또는 비밀번호가 틀렸습니다.")
            self.pw_var.set("")
            return

        stat = info["status"].upper()
        if stat not in ("활성", "ACTIVE", "1", "TRUE", "YES"):
            messagebox.showerror("로그인 실패", "비활성화된 계정입니다.")
            return

        if not self._check_expire(info["expire"]):
            messagebox.showerror("로그인 실패",
                f"계정이 만료되었습니다. (만료일: {info['expire']})")
            return

        self.authenticated = True
        self.username = uid
        messagebox.showinfo("환영합니다", f"{uid}님, 로그인 성공!")
        self.root.quit()

    def _exit(self):
        self.root.quit()

    def show(self):
        self.root.mainloop()
        if self.root.winfo_exists():
            self.root.destroy()
        return self.authenticated, self.username


# ══════════════════════════════════════════════
# CHUNK 04 — StopController + 키보드 입력 + 드래그앤드롭
# ══════════════════════════════════════════════

class StopController:
    """다중 작업 정지 이벤트 중앙 관리"""

    def __init__(self):
        self._events = {}
        self._lock   = threading.Lock()

    def register(self, key):
        with self._lock:
            if key not in self._events:
                self._events[key] = threading.Event()
            self._events[key].clear()
            return self._events[key]

    def cancel(self, key=None):
        with self._lock:
            targets = self._events.values() if key is None else \
                      ([self._events[key]] if key in self._events else [])
            for ev in targets:
                ev.set()

    def is_cancelled(self, key):
        with self._lock:
            return self._events.get(key, threading.Event()).is_set()


# ──────────────────────────────────────────────
# 키보드 입력
# ──────────────────────────────────────────────

def type_message(msg):
    """
    메시지 타이핑.
    줄바꿈(\n)은 Shift+Enter 로 처리.
    """
    lines = msg.split("\n")
    for i, line in enumerate(lines):
        if line:
            keyboard.write(line)
        if i < len(lines) - 1:
            keyboard.press_and_release("shift+enter")
            time.sleep(0.05)


# ──────────────────────────────────────────────
# 카카오톡 드래그앤드롭 이미지 첨부
# ──────────────────────────────────────────────

def kakao_drag_drop(image_source_coord, drop_coord, delays, cancel_event, logger=None):
    """
    카카오톡 내부 이미지를 드래그앤드롭으로 대상 채팅창에 전송.

    Args:
        image_source_coord : (x, y) 이미지가 있는 소스 좌표
        drop_coord         : (x, y) 드롭할 대상 좌표 (채팅 입력창)
        delays             : dict { after_image_click, after_drag_start, after_drop, after_enter }
        cancel_event       : threading.Event
        logger             : 로그 콜백 (선택)

    Returns:
        True  → 정상 완료
        False → 사용자 정지
    """
    def _log(msg):
        if logger:
            logger(msg)

    def _chk():
        return cancel_event and cancel_event.is_set()

    if not image_source_coord or not drop_coord:
        _log("[이미지] 소스/드롭 좌표 미설정 → 건너뜀")
        return True

    _log("[이미지] 드래그앤드롭 시작")

    sx, sy = image_source_coord
    tx, ty = drop_coord

    # 1. 소스 위치로 이동
    if _chk(): return False
    pyautogui.moveTo(sx, sy, duration=0.05)
    time.sleep(delays.get("after_image_click", 0.5))

    # 2. 드래그 시작 (마우스 누르기)
    if _chk(): return False
    pyautogui.mouseDown()
    time.sleep(delays.get("after_drag_start", 0.2))

    # 3. 드롭 위치로 이동
    if _chk():
        pyautogui.mouseUp()
        return False
    pyautogui.moveTo(tx, ty, duration=0.3)

    # 4. 드롭
    if _chk():
        pyautogui.mouseUp()
        return False
    pyautogui.mouseUp()
    time.sleep(delays.get("after_drop", 0.3))

    # 5. Enter (전송)
    if _chk(): return False
    pyautogui.press("enter")
    time.sleep(delays.get("after_enter", 0.5))

    _log("[이미지] 드래그앤드롭 완료")
    return True


# ══════════════════════════════════════════════
# CHUNK 05 — FloatingWorker
# ══════════════════════════════════════════════


# ============================================================
# THEME + ScrollableFrame/HoverTooltip/make_card/coord_row
# ============================================================

THEME = {
    # ── 배경 계열 ────────────────────────────
    "bg":            "#F7F8FC",   # 앱 전체 배경 (밝은 웜그레이)
    "card":          "#FFFFFF",   # 카드/입력칸 흰색
    "bar":           "#FFFFFF",   # 상단/하단 바
    "sidebar":       "#F7F8FC",

    # ── 테두리 ───────────────────────────────
    "border":        "#DDE2EE",   # 일반 테두리
    "border_focus":  "#5B6EF5",   # 포커스 테두리

    # ── 액센트 (인디고) ──────────────────────
    "accent":        "#4F63E7",
    "accent_dark":   "#3B4FC4",
    "accent_light":  "#EEF0FD",

    # ── 텍스트 ───────────────────────────────
    "text_primary":  "#1A1F36",   # 제목·중요 텍스트 (진한 네이비)
    "text_secondary":"#3D4A6B",   # 일반 텍스트
    "text_muted":    "#7A86A8",   # 흐린 텍스트
    "text_white":    "#FFFFFF",

    # ── 시맨틱 ───────────────────────────────
    "ok":            "#16A34A",
    "ok_light":      "#DCFCE7",
    "warning":       "#B45309",
    "warning_light": "#FEF3C7",
    "danger":        "#DC2626",
    "danger_light":  "#FEE2E2",

    # ── 로그 패널 ────────────────────────────
    "log_bg":        "#0F172A",
    "log_fg":        "#8892A4",
    "log_ok":        "#34D399",
    "log_warn":      "#FBBF24",
    "log_err":       "#F87171",
    "log_info":      "#60A5FA",
    "log_muted":     "#4B5563",

    # ── 도움말 패널 ──────────────────────────
    "help_bg":       "#1E293B",
    "help_fg":       "#CBD5E1",
    "help_head":     "#93C5FD",
    "help_key":      "#FCD34D",
    "help_val":      "#6EE7B7",
}


# ── 공통 위젯 헬퍼 ───────────────────────────────────────────

class ScrollableFrame(ttk.Frame):
    """수직 스크롤 가능한 컨테이너"""

    def __init__(self, parent, bg=None, **kw):
        super().__init__(parent, **kw)
        _bg = bg or THEME["bg"]
        self.canvas = tk.Canvas(self, bg=_bg, highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, style="Body.TFrame")
        self._win_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>",   self._on_frame_cfg)
        self.canvas.bind("<Configure>", self._on_canvas_cfg)
        self.body.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._scroll))
        self.body.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_frame_cfg(self, _):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_cfg(self, e):
        self.canvas.itemconfig(self._win_id, width=e.width)

    def _scroll(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")


class HoverTooltip:
    """호버 툴팁"""

    def __init__(self, widget, text, delay=600):
        self.widget = widget
        self.text   = text
        self.delay  = delay
        self._job   = None
        self._tip   = None
        widget.bind("<Enter>",       self._schedule)
        widget.bind("<Leave>",       self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, _=None):
        self._job = self.widget.after(self.delay, self._show)

    def _show(self):
        if self._tip or not self.text:
            return
        x = self.widget.winfo_pointerx() + 12
        y = self.widget.winfo_pointery() + 16
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, font=("Segoe UI", 9),
                 bg="#1E293B", fg="#CBD5E1",
                 padx=10, pady=5, relief="flat").pack()

    def _hide(self, _=None):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        if self._tip:
            self._tip.destroy()
            self._tip = None


def make_card(parent, title="", padding=(10, 8)):
    """카드형 LabelFrame"""
    lf = ttk.LabelFrame(parent, text=title, style="Card.TLabelframe")
    lf.pack(fill="x", padx=12, pady=(3, 5))
    lf.configure(padding=padding)
    return lf


def row_frame(parent, pady=2):
    """가로 정렬 프레임 (카드 배경)"""
    f = ttk.Frame(parent, style="Card.TFrame")
    f.pack(fill="x", pady=pady)
    return f


def lbl(parent, text, width=None, style="Muted.TLabel"):
    kw = {"text": text, "style": style}
    if width:
        kw["width"] = width
    return ttk.Label(parent, **kw)


def ent(parent, var, width=7, **kw):
    return ttk.Entry(parent, textvariable=var, width=width, **kw)


def coord_row(parent, label_text, var_x, var_y, pick_cmd=None, btn_text="📍 캡처"):
    """X / Y 입력 + 캡처 버튼 한 행"""
    row = ttk.Frame(parent, style="Card.TFrame")
    row.pack(fill="x", pady=2)
    lbl(row, label_text, width=14).pack(side="left")
    lbl(row, "X").pack(side="left", padx=(4, 2))
    ent(row, var_x, 6).pack(side="left", padx=(0, 6))
    lbl(row, "Y").pack(side="left", padx=(0, 2))
    ent(row, var_y, 6).pack(side="left", padx=(0, 8))
    if pick_cmd:
        ttk.Button(row, text=btn_text, style="Ghost.TButton",
                   command=pick_cmd).pack(side="left")
    return row


# 기존 FloatingWorker 클래스를 완전히 교체

class FloatingWorker:
    """플로팅 메시지 자동 발송 워커 (v2.6)"""

    def __init__(self, preset, cancel_event, logger):
        self.preset       = preset
        self.cancel_event = cancel_event
        self.logger       = logger
        self.running      = True

    def _log(self, msg):
        self.logger(msg)

    def _chk(self):
        return self.cancel_event.is_set() or not self.running

    def run(self, points, message):
        p   = self.preset
        ad  = safe_float(p.get("action_delay",   1.0), 1.0)
        gap = safe_float(p.get("between_chats",  0.0), 0.0)
        jit = safe_float(p.get("between_jitter", 0.0), 0.0)

        send_mode   = p.get("send_mode",  "enter")
        close_after = bool(p.get("close_after_send", True))
        close_mode  = p.get("close_mode", "altf4")

        use_image    = (p.get("image_mode", "none") == "files")
        image_timing = p.get("image_timing", "before")
        src_coord    = p.get("image_source_coord")
        drop_coord   = p.get("image_drop_coord")
        image_delays = p.get("image_delays", {})

        total = len(points)
        self._log(f"[시작] 대상 {total}명 | 단계간격 {ad}s | 타일간격 {gap}±{jit}s")

        try:
            for idx, (x, y) in enumerate(points, 1):
                if self._chk(): break

                self._log(f"[{idx}/{total}] 더블클릭 ({x}, {y})")

                # ① 더블클릭 → 채팅창 열기
                pyautogui.moveTo(x, y, duration=0.05)
                pyautogui.doubleClick()
                time.sleep(ad)
                if self._chk(): break

                # ② 이미지 첨부 (before)
                if use_image and image_timing == "before":
                    ok = kakao_drag_drop(src_coord, drop_coord,
                                        image_delays, self.cancel_event, self._log)
                    if not ok or self._chk(): break
                    time.sleep(ad)
                if self._chk(): break

                # ③ 메시지 타이핑 (더블클릭 후 바로)
                type_message(message)
                time.sleep(ad)
                if self._chk(): break

                # ④ 전송
                if send_mode == "enter":
                    pyautogui.press("enter")
                elif send_mode == "ctrl_enter":
                    pyautogui.hotkey("ctrl", "enter")
                else:
                    sb = p.get("send_btn")
                    if sb:
                        pyautogui.moveTo(sb[0], sb[1], duration=0.05)
                        pyautogui.click()
                    else:
                        pyautogui.press("enter")

                self._log("  ↳ 전송 완료")
                time.sleep(ad)
                if self._chk(): break

                # ⑤ 이미지 첨부 (after)
                if use_image and image_timing == "after":
                    ok = kakao_drag_drop(src_coord, drop_coord,
                                        image_delays, self.cancel_event, self._log)
                    if not ok or self._chk(): break
                    time.sleep(ad)
                if self._chk(): break

                # ⑥ 창 닫기
                if close_after:
                    if close_mode == "altf4":
                        pyautogui.hotkey("alt", "f4")
                    elif close_mode == "esc":
                        pyautogui.press("escape")
                    else:  # click_btn
                        cb = p.get("close_btn")
                        if cb:
                            pyautogui.moveTo(cb[0], cb[1], duration=0.05)
                            pyautogui.click()
                        else:
                            pyautogui.hotkey("alt", "f4")
                    self._log(f"  ↳ 창 닫기 ({close_mode})")
                    time.sleep(ad)
                if self._chk(): break

                # ⑦ 다음 대상 대기
                if idx < total and (gap or jit):
                    wait = max(0.0, gap + (random.uniform(-jit, jit) if jit > 0 else 0))
                    self._log(f"  ↳ 다음 대기 {wait:.2f}s")
                    time.sleep(wait)

            if self._chk():
                self._log("[정지] 사용자 정지")
            else:
                self._log(f"[완료] {total}명 발송 완료 ✅")

        except Exception as e:
            self._log(f"[오류] {e}")
            import traceback
            traceback.print_exc()

    def stop(self):
        self.running = False





# ============================================================
# FloatingWorker
# ============================================================


class FloatingWorker:
    """
    플로팅 메시지 자동 발송 워커 (v2.6)

    제거된 기능:
      - 메시지 입력칸 별도 클릭 → 더블클릭 후 바로 타이핑
      - 대화 저장 모드
      - 이미지 다이얼로그 방식
    """

    def __init__(self, preset, cancel_event, logger):
        self.preset       = preset
        self.cancel_event = cancel_event
        self.logger       = logger
        self.running      = True

    def _log(self, msg):
        self.logger(msg)

    def _chk(self):
        return self.cancel_event.is_set() or not self.running

    def run(self, points, message):
        """
        Args:
            points  : [(x, y), ...]  좌표 리스트
            message : str            전송할 메시지 (치환 없음)
        """
        p   = self.preset
        ad  = safe_float(p.get("action_delay",   1.0), 1.0)
        gap = safe_float(p.get("between_chats",  0.0), 0.0)
        jit = safe_float(p.get("between_jitter", 0.0), 0.0)

        send_mode   = p.get("send_mode",  "enter")
        close_after = bool(p.get("close_after_send", True))
        close_mode  = p.get("close_mode", "altf4")

        use_image    = (p.get("image_mode", "none") == "files")
        image_timing = p.get("image_timing", "before")
        src_coord    = p.get("image_source_coord")
        drop_coord   = p.get("image_drop_coord")
        image_delays = p.get("image_delays", {})

        total = len(points)
        self._log(f"[시작] 대상 {total}명 | 단계간격 {ad}s | 타일간격 {gap}±{jit}s")

        try:
            for idx, (x, y) in enumerate(points, 1):
                if self._chk(): break

                self._log(f"[{idx}/{total}] 더블클릭 ({x}, {y})")

                # ① 더블클릭 → 채팅창 열기
                pyautogui.moveTo(x, y, duration=0.05)
                pyautogui.doubleClick()
                time.sleep(ad)
                if self._chk(): break

                # ② 이미지 첨부 (before)
                if use_image and image_timing == "before":
                    ok = kakao_drag_drop(src_coord, drop_coord,
                                        image_delays, self.cancel_event, self._log)
                    if not ok or self._chk(): break
                    time.sleep(ad)
                if self._chk(): break

                # ③ 메시지 타이핑 (더블클릭 후 바로)
                type_message(message)
                time.sleep(ad)
                if self._chk(): break

                # ④ 전송
                if send_mode == "enter":
                    pyautogui.press("enter")
                elif send_mode == "ctrl_enter":
                    pyautogui.hotkey("ctrl", "enter")
                else:  # click_btn
                    sb = p.get("send_btn")
                    if sb:
                        pyautogui.moveTo(sb[0], sb[1], duration=0.05)
                        pyautogui.click()
                    else:
                        pyautogui.press("enter")

                self._log("  ↳ 전송 완료")
                time.sleep(ad)
                if self._chk(): break

                # ⑤ 이미지 첨부 (after)
                if use_image and image_timing == "after":
                    ok = kakao_drag_drop(src_coord, drop_coord,
                                        image_delays, self.cancel_event, self._log)
                    if not ok or self._chk(): break
                    time.sleep(ad)
                if self._chk(): break

                # ⑥ 창 닫기
                if close_after:
                    if close_mode == "altf4":
                        pyautogui.hotkey("alt", "f4")
                    elif close_mode == "esc":
                        pyautogui.press("escape")
                    else:  # click_btn
                        cb = p.get("close_btn")
                        if cb:
                            pyautogui.moveTo(cb[0], cb[1], duration=0.05)
                            pyautogui.click()
                        else:
                            pyautogui.hotkey("alt", "f4")
                    self._log(f"  ↳ 창 닫기 ({close_mode})")
                    time.sleep(ad)
                if self._chk(): break

                # ⑦ 다음 대상 대기
                if idx < total and (gap or jit):
                    wait = max(0.0, gap + (random.uniform(-jit, jit) if jit > 0 else 0))
                    self._log(f"  ↳ 다음 대기 {wait:.2f}s")
                    time.sleep(wait)

            if self._chk():
                self._log("[정지] 사용자 정지")
            else:
                self._log(f"[완료] {total}명 발송 완료 ✅")

        except Exception as e:
            self._log(f"[오류] {e}")
            import traceback
            traceback.print_exc()

    def stop(self):
        self.running = False



# ============================================================
# KakaoApp.__init__
# ============================================================


class KakaoApp(tk.Tk):
    """카카오톡 플로팅 자동화 v2.6 메인 윈도우"""

    def __init__(self):
        super().__init__()
        self.title("카카오톡 플로팅 자동화  v2.6")
        self.geometry("860x740")
        self.minsize(720, 580)
        self.resizable(True, True)
        self.configure(bg=THEME["bg"])
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._init_theme()
        self._init_vars()
        self._load_config()
        self._build_ui()
        self._apply_preset(self.config.get("active_preset", "default"))
        self._bind_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)



# ============================================================
# KakaoApp._init_theme
# ============================================================

    def _init_theme(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass

        BG   = THEME["bg"]
        CARD = THEME["card"]
        ACC  = THEME["accent"]
        ACCD = THEME["accent_dark"]
        SEC  = THEME["text_secondary"]
        MUT  = THEME["text_muted"]
        PRI  = THEME["text_primary"]
        DNG  = THEME["danger"]
        BRD  = THEME["border"]

        # 프레임
        st.configure("Body.TFrame",    background=BG)
        st.configure("Card.TFrame",    background=CARD)

        # LabelFrame (섹션 카드)
        st.configure("Card.TLabelframe",
                     background=CARD, borderwidth=1,
                     relief="solid", bordercolor=BRD)
        st.configure("Card.TLabelframe.Label",
                     background=CARD,
                     font=("Segoe UI Semibold", 9),
                     foreground=ACC, padding=(2, 0))

        # 체크 / 라디오
        for s in ("Card.TCheckbutton", "Body.TCheckbutton"):
            st.configure(s, background=CARD if "Card" in s else BG,
                         font=("Segoe UI", 9), foreground=SEC)
        for s in ("Card.TRadiobutton",):
            st.configure(s, background=CARD,
                         font=("Segoe UI", 9), foreground=SEC)

        # 레이블
        st.configure("Muted.TLabel",
                     background=CARD, foreground=MUT,
                     font=("Segoe UI", 9))
        st.configure("MutedBG.TLabel",
                     background=BG, foreground=MUT,
                     font=("Segoe UI", 9))
        st.configure("Sec.TLabel",
                     background=CARD, foreground=SEC,
                     font=("Segoe UI", 9))
        st.configure("Title.TLabel",
                     background=BG, foreground=PRI,
                     font=("Segoe UI Semibold", 12))
        st.configure("Badge.TLabel",
                     background=THEME["accent_light"],
                     foreground=ACC,
                     font=("Segoe UI Semibold", 9),
                     padding=(8, 3))
        st.configure("OkBadge.TLabel",
                     background=THEME["ok_light"],
                     foreground=THEME["ok"],
                     font=("Segoe UI Semibold", 9),
                     padding=(8, 3))
        st.configure("WarnBadge.TLabel",
                     background=THEME["warning_light"],
                     foreground=THEME["warning"],
                     font=("Segoe UI Semibold", 9),
                     padding=(8, 3))

        # 버튼
        st.configure("Accent.TButton",
                     padding=(10, 5), background=ACC,
                     foreground="white", font=("Segoe UI", 9))
        st.configure("Small.TButton",
                     padding=(6, 3), background=CARD,
                     foreground=SEC, font=("Segoe UI", 9))
        st.configure("Ghost.TButton",
                     padding=(6, 3), background=BG,
                     foreground=MUT, font=("Segoe UI", 9))
        st.configure("Danger.TButton",
                     padding=(6, 3), background=CARD,
                     foreground=DNG, font=("Segoe UI", 9))
        st.configure("Help.TButton",
                     padding=(6, 3), background=THEME["accent_light"],
                     foreground=ACC, font=("Segoe UI Semibold", 9))

        for style, norm, press in [
            ("Accent.TButton", ACC,  ACCD),
            ("Help.TButton",   THEME["accent_light"], THEME["accent_light"]),
        ]:
            st.map(style,
                   background=[("pressed", press), ("active", norm)],
                   foreground=[("pressed", "white"), ("active", "white"
                               if style == "Accent.TButton" else ACC)])
        st.map("Ghost.TButton",
               foreground=[("active", PRI)])
        st.map("Danger.TButton",
               foreground=[("active", DNG), ("pressed", DNG)])

        # 기타
        st.configure("TCombobox",  fieldbackground=CARD, font=("Segoe UI", 9))
        st.configure("TEntry",     fieldbackground=CARD, font=("Segoe UI", 9))
        st.configure("TSeparator", background=BRD)


# ============================================================
# KakaoApp._init_vars  (자동반복/계정 제거)
# ============================================================


    def _init_vars(self):
        # ── 좌표 계산 ─────────────────────────────
        self.v_start_x  = tk.StringVar()
        self.v_start_y  = tk.StringVar()
        self.v_cell_w   = tk.StringVar(value="200")
        self.v_cell_h   = tk.StringVar(value="30.8")
        self.v_col      = tk.StringVar(value="5")
        self.v_row      = tk.StringVar(value="4")
        self.v_col_gap  = tk.StringVar(value="46")
        self.v_scan_dir = tk.StringVar(value="col")   # "col"=열우선, "row"=행우선
        self.v_preview  = tk.StringVar(value="0개")

        # ── 동작 설정 ─────────────────────────────
        self.v_action_delay  = tk.StringVar(value="1.0")
        self.v_between_chats = tk.StringVar(value="0.0")
        self.v_jitter        = tk.StringVar(value="0.0")
        self.v_send_mode     = tk.StringVar(value="enter")
        self.v_send_btn_x    = tk.StringVar()
        self.v_send_btn_y    = tk.StringVar()
        self.v_close_after   = tk.BooleanVar(value=True)
        self.v_close_mode    = tk.StringVar(value="altf4")
        self.v_close_btn_x   = tk.StringVar()
        self.v_close_btn_y   = tk.StringVar()

        # ── 이미지 ────────────────────────────────
        self.v_image_mode   = tk.StringVar(value="none")
        self.v_image_timing = tk.StringVar(value="before")
        self.v_img_src_x    = tk.StringVar()
        self.v_img_src_y    = tk.StringVar()
        self.v_img_drop_x   = tk.StringVar()
        self.v_img_drop_y   = tk.StringVar()
        self.v_img_d_click  = tk.StringVar(value="0.5")
        self.v_img_d_drag   = tk.StringVar(value="0.2")
        self.v_img_d_drop   = tk.StringVar(value="0.3")
        self.v_img_d_enter  = tk.StringVar(value="0.5")

        # ── 프리셋 ────────────────────────────────
        self.v_preset_name = tk.StringVar()

        # ── 상태 ─────────────────────────────────
        self.v_status  = tk.StringVar(value="대기 중")
        self.v_summary = tk.StringVar(value="")

        # ── 로그 토글 ─────────────────────────────
        self.v_log_open = tk.BooleanVar(value=False)

        # ── 내부 ─────────────────────────────────
        self.sending      = False
        self._stop_ctrl   = StopController()
        self._cancel_ev   = self._stop_ctrl.register("floating")
        self._worker      = None
        self.config       = {}



# ============================================================
# KakaoApp._build_ui ~ _toggle_log
# ============================================================


    def _build_ui(self):
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)
        self.rowconfigure(3, weight=0)
        self.columnconfigure(0, weight=1)

        self._build_header()
        self._build_body()
        self._build_bottom_bar()
        self._build_log_panel()

    # ─────────────────────────────────────────
    # 헤더
    # ─────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=THEME["bar"],
                       highlightthickness=1,
                       highlightbackground=THEME["border"])
        hdr.grid(row=0, column=0, sticky="ew")

        inner = tk.Frame(hdr, bg=THEME["bar"])
        inner.pack(fill="x", padx=18, pady=11)

        # 왼쪽: 타이틀
        lf = tk.Frame(inner, bg=THEME["bar"])
        lf.pack(side="left")
        tk.Label(lf,
                 text="카카오톡 플로팅 자동화",
                 font=("Segoe UI Semibold", 13),
                 bg=THEME["bar"], fg=THEME["text_primary"]).pack(side="left")
        tk.Label(lf,
                 text="  v2.6",
                 font=("Segoe UI", 10),
                 bg=THEME["bar"], fg=THEME["text_muted"]).pack(side="left", pady=(2, 0))

        # 상태 배지
        self._status_badge = tk.Label(inner,
                 textvariable=self.v_summary,
                 font=("Segoe UI", 9),
                 bg=THEME["accent_light"], fg=THEME["accent"],
                 padx=10, pady=3)
        self._status_badge.pack(side="left", padx=14)

        # 오른쪽: 도움말 버튼 + 핫키 힌트
        ttk.Button(inner, text="❓ 도움말",
                   style="Help.TButton",
                   command=self._show_help).pack(side="right", padx=(8, 0))
        tk.Label(inner,
                 text="F6 좌표캡처  ·  F8 시작  ·  F9 정지",
                 font=("Segoe UI", 8),
                 bg=THEME["bar"], fg=THEME["text_muted"]).pack(side="right", padx=(0, 12))

    # ─────────────────────────────────────────
    # 바디 (스크롤 설정 패널)  ← schedule 섹션 제거
    # ─────────────────────────────────────────
    def _build_body(self):
        body = ttk.Frame(self, style="Body.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        scroll = ScrollableFrame(body, bg=THEME["bg"])
        scroll.grid(row=0, column=0, sticky="nsew")
        pane = scroll.body

        self._build_coord_section(pane)
        self._build_action_section(pane)
        self._build_image_section(pane)
        self._build_message_section(pane)
        # ← 자동반복(_build_schedule_section) 제거
        self._build_preset_section(pane)

        ttk.Frame(pane, style="Body.TFrame", height=16).pack()

    # ─────────────────────────────────────────
    # 하단 컨트롤 바
    # ─────────────────────────────────────────
    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg=THEME["bar"],
                       highlightthickness=1,
                       highlightbackground=THEME["border"])
        bar.grid(row=2, column=0, sticky="ew")

        inner = tk.Frame(bar, bg=THEME["bar"])
        inner.pack(fill="x", padx=16, pady=9)

        # ▶ 시작 버튼
        self.btn_run = tk.Button(
            inner,
            text="▶  시작  (F8)",
            font=("Segoe UI Semibold", 10),
            bg=THEME["accent"], fg=THEME["text_white"],
            activebackground=THEME["accent_dark"],
            activeforeground=THEME["text_white"],
            relief="flat", bd=0, padx=22, pady=8,
            cursor="hand2",
            command=lambda: threading.Thread(target=self._start, daemon=True).start()
        )
        self.btn_run.pack(side="left", padx=(0, 6))

        # ■ 정지 버튼
        self.btn_stop = tk.Button(
            inner,
            text="■  정지  (F9)",
            font=("Segoe UI Semibold", 10),
            bg=THEME["danger"], fg=THEME["text_white"],
            activebackground="#B91C1C",
            activeforeground=THEME["text_white"],
            relief="flat", bd=0, padx=22, pady=8,
            cursor="hand2",
            command=self._stop
        )
        self.btn_stop.pack(side="left", padx=(0, 14))

        # 좌표 테스트
        tk.Button(
            inner,
            text="🔵 좌표 테스트",
            font=("Segoe UI", 9),
            bg=THEME["card"], fg=THEME["text_secondary"],
            activebackground=THEME["bg"],
            relief="flat", bd=1, padx=12, pady=7,
            cursor="hand2",
            highlightbackground=THEME["border"],
            command=lambda: threading.Thread(target=self._test_clicks, daemon=True).start()
        ).pack(side="left")

        # 로그 토글 (오른쪽)
        self._log_toggle_btn = tk.Button(
            inner,
            text="📋 로그 ▼",
            font=("Segoe UI", 9),
            bg=THEME["card"], fg=THEME["text_muted"],
            activebackground=THEME["bg"],
            relief="flat", bd=1, padx=10, pady=7,
            cursor="hand2",
            command=self._toggle_log
        )
        self._log_toggle_btn.pack(side="right", padx=(6, 0))

        # 상태 텍스트
        self._status_lbl = tk.Label(
            inner,
            textvariable=self.v_status,
            font=("Segoe UI", 9),
            bg=THEME["bar"], fg=THEME["text_muted"]
        )
        self._status_lbl.pack(side="right", padx=14)

    # ─────────────────────────────────────────
    # 로그 패널 (접이식)
    # ─────────────────────────────────────────
    def _build_log_panel(self):
        self._log_frame = tk.Frame(
            self, bg=THEME["log_bg"],
            highlightthickness=1,
            highlightbackground=THEME["border"]
        )
        # 기본 숨김 (row=3 에 배치하지 않음)

        inner = tk.Frame(self._log_frame, bg=THEME["log_bg"])
        inner.pack(fill="both", expand=True, padx=2, pady=(4, 2))

        # 툴바
        tb = tk.Frame(inner, bg=THEME["log_bg"])
        tb.pack(fill="x", padx=8, pady=(2, 0))
        tk.Label(tb, text="실시간 로그",
                 font=("Segoe UI Semibold", 9),
                 bg=THEME["log_bg"], fg=THEME["log_muted"]).pack(side="left")
        tk.Button(tb, text="지우기",
                  font=("Segoe UI", 8),
                  bg=THEME["log_bg"], fg=THEME["log_muted"],
                  activebackground=THEME["log_bg"],
                  relief="flat", bd=0, padx=6, pady=2,
                  cursor="hand2",
                  command=self._clear_log).pack(side="right")

        # 텍스트
        self.log_text = tk.Text(
            inner, height=8,
            wrap="word",
            font=("Consolas", 9),
            bg=THEME["log_bg"], fg=THEME["log_fg"],
            insertbackground=THEME["log_fg"],
            relief="flat", bd=0, padx=10, pady=6,
            highlightthickness=0, state="disabled"
        )
        log_sb = tk.Scrollbar(inner, orient="vertical",
                              command=self.log_text.yview,
                              bg=THEME["log_bg"], troughcolor="#1E293B", width=10)
        self.log_text.configure(yscrollcommand=log_sb.set)
        log_sb.pack(side="right", fill="y", pady=4)
        self.log_text.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)

        for tag, color in [
            ("ok",    THEME["log_ok"]),
            ("warn",  THEME["log_warn"]),
            ("err",   THEME["log_err"]),
            ("info",  THEME["log_info"]),
            ("muted", THEME["log_fg"]),
        ]:
            self.log_text.tag_configure(tag, foreground=color)

    def _toggle_log(self):
        if self.v_log_open.get():
            self._log_frame.grid_forget()
            self.v_log_open.set(False)
            self._log_toggle_btn.configure(text="📋 로그 ▼")
        else:
            self._log_frame.grid(row=3, column=0, sticky="ew")
            self.v_log_open.set(True)
            self._log_toggle_btn.configure(text="📋 로그 ▲")



# ============================================================
# KakaoApp 섹션 빌더 (ESC 닫기, 계정치환 제거)
# ============================================================


    def _build_coord_section(self, parent):
        card = make_card(parent, "🎯  좌표 자동 계산")

        # 시작 좌표
        r0 = row_frame(card)
        lbl(r0, "시작 좌표", width=10).pack(side="left")
        lbl(r0, "X").pack(side="left", padx=(6, 2))
        ent(r0, self.v_start_x, 7).pack(side="left", padx=(0, 6))
        lbl(r0, "Y").pack(side="left", padx=(0, 2))
        ent(r0, self.v_start_y, 7).pack(side="left", padx=(0, 10))
        ttk.Button(r0, text="📍 캡처 (F6)", style="Ghost.TButton",
                   command=lambda: threading.Thread(
                       target=self._pick_point, args=("start", "시작 좌표"),
                       daemon=True).start()).pack(side="left")

        # 셀 크기
        r1 = row_frame(card)
        lbl(r1, "1칸 크기", width=10).pack(side="left")
        lbl(r1, "가로").pack(side="left", padx=(6, 2))
        ent(r1, self.v_cell_w, 6).pack(side="left", padx=(0, 8))
        lbl(r1, "세로").pack(side="left", padx=(0, 2))
        ent(r1, self.v_cell_h, 6).pack(side="left", padx=(0, 4))
        lbl(r1, "px").pack(side="left")

        # 구성 (열 / 행 / 열간격)
        r2 = row_frame(card)
        lbl(r2, "구성", width=10).pack(side="left")
        for text, var, unit in [
            ("열",    self.v_col,    ""),
            ("행",    self.v_row,    ""),
            ("열간격", self.v_col_gap, "px"),
        ]:
            lbl(r2, text).pack(side="left", padx=(6, 2))
            ent(r2, var, 5).pack(side="left", padx=(0, 2))
            if unit:
                lbl(r2, unit).pack(side="left", padx=(0, 2))

        # 스캔 방향
        r2b = row_frame(card)
        lbl(r2b, "방향", width=10).pack(side="left")
        ttk.Radiobutton(r2b, text="열 우선  (↓→)", value="col",
                        variable=self.v_scan_dir,
                        style="Card.TRadiobutton").pack(side="left", padx=(6, 0))
        ttk.Radiobutton(r2b, text="행 우선  (→↓)", value="row",
                        variable=self.v_scan_dir,
                        style="Card.TRadiobutton").pack(side="left", padx=(8, 0))
        HoverTooltip(r2b,
            "열 우선(↓→): 한 열을 위→아래로 처리 후 다음 열\n"
            "행 우선(→↓): 한 행을 좌→우로 처리 후 다음 행")

        # 미리보기
        r3 = row_frame(card, pady=(6, 2))
        r3.configure(style="Body.TFrame")
        ttk.Label(r3, textvariable=self.v_preview, style="Badge.TLabel").pack(side="left")
        ttk.Button(r3, text="↺ 계산", style="Ghost.TButton",
                   command=self._update_preview).pack(side="left", padx=(6, 0))
        for v in (self.v_col, self.v_row):
            v.trace_add("write", lambda *_: self._update_preview())
        self.v_scan_dir.trace_add("write", lambda *_: self._update_preview())


    def _build_action_section(self, parent):
        card = make_card(parent, "⚙️  동작 설정")

        # 타이밍
        r0 = row_frame(card)
        lbl(r0, "타이밍", width=10).pack(side="left")
        for text, var, unit in [
            ("단계",  self.v_action_delay,  "s"),
            ("타일",  self.v_between_chats, "s"),
            ("±랜덤", self.v_jitter,        "s"),
        ]:
            lbl(r0, text).pack(side="left", padx=(10, 2))
            ent(r0, var, 5).pack(side="left", padx=(0, 1))
            lbl(r0, unit).pack(side="left")

        # 전송 방식
        r1 = row_frame(card)
        lbl(r1, "전송", width=10).pack(side="left")
        for text, val in [("Enter", "enter"), ("Ctrl+Enter", "ctrl_enter"), ("버튼 클릭", "click_btn")]:
            ttk.Radiobutton(r1, text=text, value=val,
                            variable=self.v_send_mode,
                            style="Card.TRadiobutton").pack(side="left", padx=(6, 0))

        coord_row(card, "전송버튼 좌표",
                  self.v_send_btn_x, self.v_send_btn_y,
                  pick_cmd=lambda: threading.Thread(
                      target=self._pick_point, args=("send_btn", "전송 버튼"),
                      daemon=True).start())

        # 닫기 — ESC 옵션 추가
        r2 = row_frame(card)
        ttk.Checkbutton(r2, text="전송 후 창 닫기",
                        variable=self.v_close_after,
                        style="Card.TCheckbutton").pack(side="left")
        lbl(r2, "방식").pack(side="left", padx=(16, 2))
        for text, val in [("Alt+F4", "altf4"), ("ESC", "esc"), ("버튼", "click_btn")]:
            ttk.Radiobutton(r2, text=text, value=val,
                            variable=self.v_close_mode,
                            style="Card.TRadiobutton").pack(side="left", padx=(4, 0))

        coord_row(card, "닫기버튼 좌표",
                  self.v_close_btn_x, self.v_close_btn_y,
                  pick_cmd=lambda: threading.Thread(
                      target=self._pick_point, args=("close_btn", "닫기 버튼"),
                      daemon=True).start())


    def _build_image_section(self, parent):
        card = make_card(parent, "🖼️  이미지 첨부  (드래그앤드롭)")

        r0 = row_frame(card)
        lbl(r0, "이미지", width=10).pack(side="left")
        ttk.Radiobutton(r0, text="사용", value="files",
                        variable=self.v_image_mode,
                        style="Card.TRadiobutton").pack(side="left", padx=(6, 0))
        ttk.Radiobutton(r0, text="사용 안 함", value="none",
                        variable=self.v_image_mode,
                        style="Card.TRadiobutton").pack(side="left", padx=(4, 0))
        lbl(r0, "타이밍").pack(side="left", padx=(16, 2))
        ttk.Radiobutton(r0, text="텍스트 전", value="before",
                        variable=self.v_image_timing,
                        style="Card.TRadiobutton").pack(side="left", padx=(4, 0))
        ttk.Radiobutton(r0, text="텍스트 후", value="after",
                        variable=self.v_image_timing,
                        style="Card.TRadiobutton").pack(side="left", padx=(4, 0))

        coord_row(card, "소스 좌표",
                  self.v_img_src_x, self.v_img_src_y,
                  pick_cmd=lambda: threading.Thread(
                      target=self._pick_point, args=("image_source_coord", "이미지 소스"),
                      daemon=True).start())
        coord_row(card, "드롭 좌표",
                  self.v_img_drop_x, self.v_img_drop_y,
                  pick_cmd=lambda: threading.Thread(
                      target=self._pick_point, args=("image_drop_coord", "드롭 좌표"),
                      daemon=True).start())

        r1 = row_frame(card, pady=(6, 2))
        lbl(r1, "딜레이(s)", width=10).pack(side="left")
        for text, var in [
            ("클릭후", self.v_img_d_click), ("드래그후", self.v_img_d_drag),
            ("드롭후",  self.v_img_d_drop),  ("Enter후",  self.v_img_d_enter),
        ]:
            lbl(r1, text).pack(side="left", padx=(6, 2))
            ent(r1, var, 5).pack(side="left", padx=(0, 2))


    def _build_message_section(self, parent):
        """메시지 입력 섹션 — 계정 치환 기능 제거"""
        card = make_card(parent, "📝  메시지")

        msg_wrap = ttk.Frame(card, style="Card.TFrame")
        msg_wrap.pack(fill="x", pady=(0, 6))

        self.msg_text = tk.Text(
            msg_wrap, height=5,
            font=("Segoe UI", 10),
            bg=THEME["card"], fg=THEME["text_primary"],
            insertbackground=THEME["accent"],
            relief="flat", bd=0, padx=8, pady=6,
            highlightthickness=1,
            highlightbackground=THEME["border"],
            highlightcolor=THEME["accent"],
            wrap="word"
        )
        msg_sb = ttk.Scrollbar(msg_wrap, orient="vertical", command=self.msg_text.yview)
        self.msg_text.configure(yscrollcommand=msg_sb.set)
        msg_sb.pack(side="right", fill="y")
        self.msg_text.pack(side="left", fill="both", expand=True)

        # 안내 텍스트 (계정 치환 없음)
        lbl(card, "줄바꿈: Shift+Enter 로 전송됩니다").pack(anchor="w", padx=4, pady=(2, 0))


    def _build_preset_section(self, parent):
        """프리셋 CRUD 섹션 — Config/ 폴더 기반"""
        card = make_card(parent, "💾  프리셋  (Config 폴더 저장)")

        # 이름 + 저장 행
        r0 = row_frame(card)
        lbl(r0, "이름").pack(side="left", padx=(0, 6))
        ttk.Entry(r0, textvariable=self.v_preset_name, width=16).pack(side="left", padx=(0, 6))
        ttk.Button(r0, text="💾 저장", style="Accent.TButton",
                   command=self._save_preset).pack(side="left", padx=(0, 4))
        refresh_btn = ttk.Button(r0, text="↺", style="Ghost.TButton",
                                 command=self._refresh_presets, width=2)
        refresh_btn.pack(side="left")
        HoverTooltip(refresh_btn, "목록 새로고침 (Config/presets/)")

        # 불러오기 / 삭제 행
        r1 = row_frame(card, pady=(6, 2))
        self.preset_box = ttk.Combobox(r1, state="readonly", width=18)
        self.preset_box.pack(side="left", padx=(0, 6))
        ttk.Button(r1, text="불러오기", style="Small.TButton",
                   command=self._load_preset).pack(side="left", padx=(0, 4))
        ttk.Button(r1, text="파일 가져오기", style="Ghost.TButton",
                   command=self._load_preset_file).pack(side="left", padx=(0, 4))
        ttk.Button(r1, text="삭제", style="Danger.TButton",
                   command=self._delete_preset).pack(side="left")

        # 저장 경로 표시
        r2 = row_frame(card, pady=(4, 2))
        path_lbl = tk.Label(r2, text=f"저장 위치: {get_config_dir()}",
                            font=("Segoe UI", 8),
                            bg=THEME["card"], fg=THEME["text_muted"],
                            cursor="hand2", wraplength=480, anchor="w", justify="left")
        path_lbl.pack(side="left", fill="x")



# ============================================================
# KakaoApp._show_help (자동반복/계정 섹션 제거)
# ============================================================


    def _show_help(self):
        """도움말 창 (현재 설정 기반 로직 설명)"""
        win = tk.Toplevel(self)
        win.title("도움말 — 현재 설정 로직")
        win.geometry("640x580")
        win.resizable(False, True)
        win.configure(bg=THEME["help_bg"])
        win.transient(self)
        win.grab_set()

        # ── 헤더 ───────────────────────────────
        hdr = tk.Frame(win, bg=THEME["accent"], pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="❓  도움말  /  현재 설정 로직",
                 font=("Segoe UI Semibold", 12),
                 bg=THEME["accent"], fg="white").pack()

        # ── 스크롤 본문 ─────────────────────────
        frame = tk.Frame(win, bg=THEME["help_bg"])
        frame.pack(fill="both", expand=True, padx=0, pady=0)

        txt = tk.Text(
            frame,
            font=("Consolas", 9),
            bg=THEME["help_bg"], fg=THEME["help_fg"],
            relief="flat", bd=0,
            padx=20, pady=14,
            wrap="word",
            state="normal",
            highlightthickness=0,
            spacing1=2, spacing3=4,
        )
        sb = tk.Scrollbar(frame, orient="vertical", command=txt.yview,
                          bg=THEME["help_bg"], troughcolor="#263347", width=10)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        # 태그 정의
        txt.tag_configure("h1",    font=("Segoe UI Semibold", 11),
                          foreground=THEME["help_head"], spacing1=10, spacing3=4)
        txt.tag_configure("h2",    font=("Segoe UI Semibold", 9),
                          foreground=THEME["help_key"],  spacing1=6, spacing3=2)
        txt.tag_configure("val",   font=("Consolas", 9),
                          foreground=THEME["help_val"])
        txt.tag_configure("body",  font=("Segoe UI", 9),
                          foreground=THEME["help_fg"])
        txt.tag_configure("note",  font=("Segoe UI", 9),
                          foreground=THEME["log_warn"])
        txt.tag_configure("sep",   font=("Segoe UI", 8),
                          foreground=THEME["log_muted"])

        def h1(t): txt.insert("end", f"\n{t}\n", "h1")
        def kv(k, v): txt.insert("end", f"    {k:<18}", "body"); txt.insert("end", f"{v}\n", "val")
        def note(t): txt.insert("end", f"  ⚠  {t}\n", "note")
        def line(): txt.insert("end", "  " + "─" * 52 + "\n", "sep")

        # ── 현재 프리셋 읽기 ──────────────────
        p    = self._active_preset()
        name = self.config.get("active_preset", "default")

        # ① 좌표
        h1("① 좌표 계산")
        line()
        c  = safe_int(self.v_col.get(),    5)
        r  = safe_int(self.v_row.get(),    4)
        cw = safe_float(self.v_cell_w.get(), 46)
        ch = safe_float(self.v_cell_h.get(), 30.8)
        cg = safe_float(self.v_col_gap.get(), 46)
        sd = self.v_scan_dir.get()
        start = p.get("start")
        kv("프리셋", name)
        kv("시작 좌표", f"{start}" if start else "❌ 미설정")
        kv("1칸 크기", f"가로 {cw}px  /  세로 {ch}px")
        kv("구성", f"열 {c}  ×  행 {r}")
        kv("열 간격", f"{cg}px")
        scan_label = "열 우선 (↓→)" if sd == "col" else "행 우선 (→↓)"
        kv("스캔 방향", scan_label)
        kv("총 대상 수", f"{c * r}명")
        if not start:
            note("시작 좌표가 없습니다. F6 으로 캡처하세요.")

        # ② 동작 흐름
        h1("② 1회 실행 흐름")
        line()
        send_mode  = p.get("send_mode", "enter")
        close_mode = p.get("close_mode", "altf4")
        close_on   = bool(p.get("close_after_send", True))
        ad  = p.get("action_delay",  1.0)
        gap = p.get("between_chats", 0.0)
        jit = p.get("between_jitter", 0.0)
        img_mode   = p.get("image_mode",   "none")
        img_timing = p.get("image_timing", "before")

        steps = []
        steps.append(("더블클릭 (채팅창 열기)", f"대기 {ad}s"))
        if img_mode == "files" and img_timing == "before":
            steps.append(("이미지 드래그앤드롭", f"대기 {ad}s"))
        steps.append(("메시지 타이핑", f"더블클릭 직후 바로 입력  /  대기 {ad}s"))
        send_str = {"enter": "Enter 키", "ctrl_enter": "Ctrl+Enter",
                    "click_btn": f"버튼 클릭 {p.get('send_btn')}"}
        steps.append(("전송", f"{send_str.get(send_mode, send_mode)}  /  대기 {ad}s"))
        if img_mode == "files" and img_timing == "after":
            steps.append(("이미지 드래그앤드롭", f"대기 {ad}s"))
        if close_on:
            close_str = {"altf4": "Alt+F4", "esc": "ESC 키",
                         "click_btn": f"버튼 클릭 {p.get('close_btn')}"}
            steps.append(("창 닫기", f"{close_str.get(close_mode, close_mode)}  /  대기 {ad}s"))
        steps.append(("다음 좌표까지 대기", f"{gap}s  ±  {jit}s 랜덤"))

        for i, (step, desc) in enumerate(steps, 1):
            kv(f"  {i}. {step}", desc)

        # ③ 이미지 설정
        h1("③ 이미지 설정")
        line()
        if img_mode == "files":
            src = p.get("image_source_coord")
            drp = p.get("image_drop_coord")
            d   = p.get("image_delays", {})
            kv("상태", "✅ 사용")
            kv("타이밍", "텍스트 전" if img_timing == "before" else "텍스트 후")
            kv("소스 좌표", f"{src}" if src else "❌ 미설정")
            kv("드롭 좌표", f"{drp}" if drp else "❌ 미설정")
            kv("딜레이", f"클릭후 {d.get('after_image_click',0.5)}s  드래그후 {d.get('after_drag_start',0.2)}s  드롭후 {d.get('after_drop',0.3)}s")
            if not src or not drp:
                note("소스/드롭 좌표 중 미설정 항목이 있습니다.")
        else:
            kv("상태", "사용 안 함")

        # ④ 메시지
        h1("④ 메시지")
        line()
        msg = self.msg_text.get("1.0", "end").strip() if hasattr(self, "msg_text") else ""
        kv("길이", f"{len(msg)}자")
        kv("줄바꿈 전송", "Shift+Enter → 전송")
        if not msg:
            note("메시지가 비어 있습니다.")

        # ⑤ 프리셋 저장 경로
        h1("⑤ 프리셋 / Config 저장 경로")
        line()
        kv("Config 폴더", get_config_dir())
        kv("설정 파일", get_config_path())
        kv("현재 프리셋", name)
        presets = list(self.config.get("presets", {}).keys())
        kv("등록된 프리셋", f"{len(presets)}개  " + ", ".join(presets))

        # ⑥ 핫키
        h1("⑥ 단축키")
        line()
        kv("F6", "시작 좌표 캡처 (3초 카운트다운)")
        kv("F8", "자동화 시작")
        kv("F9", "자동화 정지")

        txt.configure(state="disabled")

        # ── 닫기 버튼 ──────────────────────────
        tk.Button(win, text="닫기",
                  font=("Segoe UI", 10),
                  bg=THEME["accent"], fg="white",
                  activebackground=THEME["accent_dark"],
                  relief="flat", bd=0, padx=24, pady=8,
                  cursor="hand2",
                  command=win.destroy).pack(pady=12)
        win.bind("<Escape>", lambda e: win.destroy())



# ============================================================
# log/_clear_log/_pick_point/_update_preview/_bind_hotkeys/_update_summary
# ============================================================


    def log(self, msg: str):
        """로그 출력 (태그 자동 선택)"""
        def _write():
            self.log_text.configure(state="normal")
            ts  = datetime.now().strftime("%H:%M:%S")
            tag = "muted"
            low = msg.lower()
            if any(k in low for k in ("완료", "성공", "ok")):
                tag = "ok"
            elif any(k in low for k in ("오류", "error", "실패")):
                tag = "err"
            elif any(k in low for k in ("경고", "warn", "주의")):
                tag = "warn"
            elif any(k in low for k in ("시작", "정지", "안내", "info", "대기")):
                tag = "info"
            self.log_text.insert("end", f"[{ts}] {msg}\n", tag)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(0, _write)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _set_status(self, msg: str):
        self.after(0, lambda: self.v_status.set(msg))

    # ──────────────────────────────────────────
    # 좌표 캡처
    # ──────────────────────────────────────────
    def _pick_point(self, key, label):
        """3초 카운트다운 후 마우스 위치 기록"""
        self.log(f"[안내] {label} 캡처 대기: 3초 후 기록합니다")
        for i in range(3, 0, -1):
            self.log(f"  {i}...")
            time.sleep(1)

        pos = pyautogui.position()
        px, py = pos.x, pos.y
        preset = self._active_preset()

        if key == "start":
            preset["start"] = [px, py]
            self.v_start_x.set(str(px))
            self.v_start_y.set(str(py))
        elif key == "send_btn":
            preset["send_btn"] = [px, py]
            self.v_send_btn_x.set(str(px))
            self.v_send_btn_y.set(str(py))
        elif key == "close_btn":
            preset["close_btn"] = [px, py]
            self.v_close_btn_x.set(str(px))
            self.v_close_btn_y.set(str(py))
        elif key == "image_source_coord":
            preset["image_source_coord"] = [px, py]
            self.v_img_src_x.set(str(px))
            self.v_img_src_y.set(str(py))
        elif key == "image_drop_coord":
            preset["image_drop_coord"] = [px, py]
            self.v_img_drop_x.set(str(px))
            self.v_img_drop_y.set(str(py))

        self._save_config()
        self.log(f"[획득] {label}: ({px}, {py})")
        self._update_summary()

    # ──────────────────────────────────────────
    # 미리보기
    # ──────────────────────────────────────────
    def _update_preview(self):
        try:
            c     = safe_int(self.v_col.get(), 5)
            r     = safe_int(self.v_row.get(), 4)
            total = c * r
            direction = "열우선(↓→)" if self.v_scan_dir.get() == "col" else "행우선(→↓)"
            self.v_preview.set(f"열 {c} × 행 {r} = 총 {total}개  [{direction}]")
        except Exception:
            self.v_preview.set("계산 오류")

    # ──────────────────────────────────────────
    # 핫키
    # ──────────────────────────────────────────
    def _bind_hotkeys(self):
        try:
            keyboard.add_hotkey("f6", lambda: threading.Thread(
                target=self._pick_point, args=("start", "시작 좌표"), daemon=True).start())
            keyboard.add_hotkey("f8", lambda: threading.Thread(
                target=self._start, daemon=True).start())
            keyboard.add_hotkey("f9", self._stop)
        except Exception:
            pass

    # ──────────────────────────────────────────
    # 요약 (헤더 배지)
    # ──────────────────────────────────────────
    def _update_summary(self):
        p = self._active_preset()
        name  = self.config.get("active_preset", "default")
        c     = safe_int(self.v_col.get(), 5)
        r     = safe_int(self.v_row.get(), 4)
        total = c * r
        start_ok = "✅" if p.get("start") else "❌"
        self.after(0, lambda: self.v_summary.set(
            f"{name}  |  {total}개 좌표  |  시작점 {start_ok}"
        ))



# ============================================================
# _default_preset/_load_config/_save_config/_collect_preset/_apply_preset/CRUD
# ============================================================


    # ══════════════════════════════════════════
    # Config / 프리셋 관리  (Config/ 폴더 기반)
    # ══════════════════════════════════════════

    def _default_preset(self):
        """기본 프리셋 값 반환"""
        return {
            "start":              None,
            "cell_width":         46,
            "cell_height":        30.8,
            "column_count":       5,
            "row_count":          4,
            "column_gap":         46,
            "scan_dir":           "col",
            "action_delay":       1.0,
            "between_chats":      0.0,
            "between_jitter":     0.0,
            "send_mode":          "enter",
            "send_btn":           None,
            "close_after_send":   True,
            "close_mode":         "altf4",
            "close_btn":          None,
            "message":            "",
            "image_mode":         "none",
            "image_timing":       "before",
            "image_source_coord": None,
            "image_drop_coord":   None,
            "image_delays": {
                "after_image_click": 0.5,
                "after_drag_start":  0.2,
                "after_drop":        0.3,
                "after_enter":       0.5,
            },
        }

    def _load_config(self):
        """
        Config/config.json 을 읽어 self.config 에 로드.
        - 파일이 없으면 기본값으로 초기화.
        - 개별 프리셋 파일(Config/presets/*.json)도 병합.
        """
        cfg_path = get_config_path()
        preset_dir = get_preset_dir()

        # ① 메인 config.json 로드
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                # 누락 키 보정
                for p_data in self.config.get("presets", {}).values():
                    for k, v in self._default_preset().items():
                        p_data.setdefault(k, v)
            except Exception:
                self.config = {}

        if not self.config:
            self.config = {
                "active_preset": "default",
                "presets":       {"default": self._default_preset()},
            }

        # "presets" 키 보장
        self.config.setdefault("presets", {"default": self._default_preset()})
        self.config.setdefault("active_preset", "default")

        # ② Config/presets/ 폴더의 개별 JSON 병합
        if os.path.isdir(preset_dir):
            for fname in os.listdir(preset_dir):
                if not fname.endswith(".json"):
                    continue
                pname = fname[:-5]  # 확장자 제거
                fpath = os.path.join(preset_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        p_data = json.load(f)
                    # 기본값으로 누락 키 보정
                    for k, v in self._default_preset().items():
                        p_data.setdefault(k, v)
                    if pname not in self.config["presets"]:
                        self.config["presets"][pname] = p_data
                except Exception:
                    pass

    def _save_config(self):
        """
        self.config 를 Config/config.json 에 저장.
        동시에 변경된 프리셋을 Config/presets/<이름>.json 에도 저장.
        """
        cfg_path   = get_config_path()
        preset_dir = get_preset_dir()

        # 메인 config 저장
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"[경고] config.json 저장 실패: {e}")
            return

        # 개별 프리셋 파일 동기화
        for p_name, p_data in self.config.get("presets", {}).items():
            safe  = sanitize_name(p_name)
            fpath = os.path.join(preset_dir, f"{safe}.json")
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(p_data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def _active_preset(self):
        name = self.config.get("active_preset", "default")
        return self.config["presets"].setdefault(name, self._default_preset())

    # ──────────────────────────────────────────
    # UI → 프리셋 수집 (계정 정보 없음)
    # ──────────────────────────────────────────
    def _collect_preset(self):
        p  = self._active_preset()
        dp = self._default_preset()

        def _coord(xv, yv, fallback=None):
            xs, ys = xv.get().strip(), yv.get().strip()
            return [safe_int(xs), safe_int(ys)] if (xs and ys) else fallback

        p.update({
            "cell_width":       safe_float(self.v_cell_w.get(),   dp["cell_width"]),
            "cell_height":      safe_float(self.v_cell_h.get(),   dp["cell_height"]),
            "column_count":     safe_int(self.v_col.get(),        dp["column_count"]),
            "row_count":        safe_int(self.v_row.get(),        dp["row_count"]),
            "column_gap":       safe_float(self.v_col_gap.get(),  dp["column_gap"]),
            "scan_dir":         self.v_scan_dir.get(),
            "action_delay":     safe_float(self.v_action_delay.get(),  dp["action_delay"]),
            "between_chats":    safe_float(self.v_between_chats.get(), dp["between_chats"]),
            "between_jitter":   safe_float(self.v_jitter.get(),        dp["between_jitter"]),
            "send_mode":        self.v_send_mode.get(),
            "send_btn":         _coord(self.v_send_btn_x, self.v_send_btn_y, p.get("send_btn")),
            "close_after_send": bool(self.v_close_after.get()),
            "close_mode":       self.v_close_mode.get(),
            "close_btn":        _coord(self.v_close_btn_x, self.v_close_btn_y, p.get("close_btn")),
            "message":          self.msg_text.get("1.0", "end").strip(),
            "image_mode":       self.v_image_mode.get(),
            "image_timing":     self.v_image_timing.get(),
            "image_source_coord": _coord(self.v_img_src_x, self.v_img_src_y,
                                         p.get("image_source_coord")),
            "image_drop_coord": _coord(self.v_img_drop_x, self.v_img_drop_y,
                                       p.get("image_drop_coord")),
            "image_delays": {
                "after_image_click": safe_float(self.v_img_d_click.get(), 0.5),
                "after_drag_start":  safe_float(self.v_img_d_drag.get(),  0.2),
                "after_drop":        safe_float(self.v_img_d_drop.get(),  0.3),
                "after_enter":       safe_float(self.v_img_d_enter.get(), 0.5),
            },
        })
        return p

    # ──────────────────────────────────────────
    # UI ← 프리셋 적용 (계정 정보 없음)
    # ──────────────────────────────────────────
    def _apply_preset(self, name):
        if name not in self.config.get("presets", {}):
            name = "default"
        self.config["active_preset"] = name
        p = self.config["presets"][name]

        def _coord_set(coord, xv, yv):
            if coord and len(coord) >= 2:
                xv.set(str(coord[0])); yv.set(str(coord[1]))
            else:
                xv.set(""); yv.set("")

        # 시작 좌표
        start = p.get("start")
        if start and len(start) >= 2:
            self.v_start_x.set(str(start[0]))
            self.v_start_y.set(str(start[1]))
        else:
            self.v_start_x.set("")
            self.v_start_y.set("")

        self.v_cell_w.set(str(p.get("cell_width",   46)))
        self.v_cell_h.set(str(p.get("cell_height",  30.8)))
        self.v_col.set(str(p.get("column_count",    5)))
        self.v_row.set(str(p.get("row_count",       4)))
        self.v_col_gap.set(str(p.get("column_gap",  46)))
        self.v_scan_dir.set(p.get("scan_dir", "col"))

        self.v_action_delay.set(str(p.get("action_delay",   1.0)))
        self.v_between_chats.set(str(p.get("between_chats", 0.0)))
        self.v_jitter.set(str(p.get("between_jitter",       0.0)))
        self.v_send_mode.set(p.get("send_mode", "enter"))
        _coord_set(p.get("send_btn"),  self.v_send_btn_x,  self.v_send_btn_y)
        self.v_close_after.set(bool(p.get("close_after_send", True)))
        self.v_close_mode.set(p.get("close_mode", "altf4"))
        _coord_set(p.get("close_btn"), self.v_close_btn_x, self.v_close_btn_y)

        self.msg_text.delete("1.0", "end")
        self.msg_text.insert("1.0", p.get("message", ""))

        self.v_image_mode.set(p.get("image_mode",   "none"))
        self.v_image_timing.set(p.get("image_timing", "before"))
        _coord_set(p.get("image_source_coord"), self.v_img_src_x, self.v_img_src_y)
        _coord_set(p.get("image_drop_coord"),   self.v_img_drop_x, self.v_img_drop_y)
        d = p.get("image_delays", {})
        self.v_img_d_click.set(str(d.get("after_image_click", 0.5)))
        self.v_img_d_drag.set(str(d.get("after_drag_start",  0.2)))
        self.v_img_d_drop.set(str(d.get("after_drop",        0.3)))
        self.v_img_d_enter.set(str(d.get("after_enter",      0.5)))

        self.v_preset_name.set(name)
        self._update_preview()
        self._update_summary()

    # ──────────────────────────────────────────
    # 프리셋 CRUD
    # ──────────────────────────────────────────
    def _refresh_presets(self):
        """Config 폴더 기반으로 목록 새로고침"""
        # 개별 파일도 스캔해서 병합
        preset_dir = get_preset_dir()
        if os.path.isdir(preset_dir):
            for fname in os.listdir(preset_dir):
                if not fname.endswith(".json"):
                    continue
                pname = fname[:-5]
                fpath = os.path.join(preset_dir, fname)
                if pname not in self.config.get("presets", {}):
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            p_data = json.load(f)
                        for k, v in self._default_preset().items():
                            p_data.setdefault(k, v)
                        self.config["presets"][pname] = p_data
                    except Exception:
                        pass

        names = sorted(self.config.get("presets", {}).keys())
        self.preset_box.configure(values=names)
        cur = self.config.get("active_preset", "default")
        if cur in names:
            self.preset_box.current(names.index(cur))

    def _save_preset(self):
        name = self.v_preset_name.get().strip()
        if not name:
            messagebox.showwarning("이름 필요", "프리셋 이름을 입력하세요.")
            return
        self._collect_preset()
        self.config["presets"][name] = self._active_preset().copy()
        self.config["active_preset"] = name
        self._save_config()
        self._refresh_presets()
        self._update_summary()
        self.log(f"[프리셋] 저장: {name}  →  Config/presets/{sanitize_name(name)}.json")

    def _load_preset(self):
        name = self.preset_box.get().strip()
        if not name or name not in self.config.get("presets", {}):
            messagebox.showwarning("없음", "목록에서 프리셋을 선택하세요.")
            return
        self._apply_preset(name)
        self.log(f"[프리셋] 불러오기: {name}")

    def _load_preset_file(self):
        """외부 JSON 파일에서 프리셋 가져오기"""
        path = filedialog.askopenfilename(
            title="프리셋 JSON 선택",
            initialdir=get_preset_dir(),
            filetypes=[("JSON", "*.json"), ("모든 파일", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 단일 프리셋 형식 {"cell_width":..., ...} 허용
            if "presets" in data:
                imported = data["presets"]
            elif "cell_width" in data or "start" in data:
                pname = os.path.splitext(os.path.basename(path))[0]
                imported = {pname: data}
            else:
                messagebox.showwarning("형식 오류", "올바른 프리셋 파일이 아닙니다.")
                return

            self.config["presets"].update(imported)
            first = next(iter(imported))
            self.config["active_preset"] = first
            self._apply_preset(first)
            self._save_config()
            self._refresh_presets()
            self.log(f"[프리셋] 파일 가져오기: {os.path.basename(path)}  ({len(imported)}개)")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _delete_preset(self):
        name = self.preset_box.get().strip()
        if not name or name not in self.config.get("presets", {}):
            messagebox.showwarning("없음", "삭제할 프리셋을 선택하세요.")
            return
        if name == "default":
            messagebox.showwarning("불가", "default는 삭제할 수 없습니다.")
            return
        if messagebox.askyesno("확인", f"'{name}' 프리셋을 삭제할까요?"):
            del self.config["presets"][name]
            # 개별 파일도 삭제
            fpath = os.path.join(get_preset_dir(), f"{sanitize_name(name)}.json")
            try:
                if os.path.exists(fpath):
                    os.remove(fpath)
            except Exception:
                pass
            self.config["active_preset"] = "default"
            self._save_config()
            self._refresh_presets()
            self._apply_preset("default")
            self.log(f"[프리셋] 삭제: {name}")



# ============================================================
# _compute_points/_start/_stop/_test_clicks/_build_message/_on_close
# ============================================================


    # ──────────────────────────────────────────
    # 좌표 계산
    # ──────────────────────────────────────────
    def _compute_points(self):
        """프리셋 기반 좌표 리스트 생성
        열우선(↓→): 한 열을 위→아래로 수직 처리 후 다음 열로 이동
        행우선(→↓): 한 행을 좌→우로 수평 처리 후 다음 행으로 이동
        좌표: x = sx + col * col_gap
                 y = sy + row * cell_h
        """
        p = self._active_preset()
        start = p.get("start")
        if not start or len(start) < 2:
            return None, "시작 좌표가 설정되지 않았습니다."

        sx, sy     = start[0], start[1]
        cell_h     = safe_float(self.v_cell_h.get(),   30.8)
        col_cnt    = safe_int(self.v_col.get(),        5)
        row_cnt    = safe_int(self.v_row.get(),        4)
        col_gap    = safe_float(self.v_col_gap.get(),  46)
        scan_dir   = self.v_scan_dir.get()   # "col" or "row"

        points = []
        if scan_dir == "col":
            # 열 우선 (↓→): col0의 row0~N → col1의 row0~N → ...
            for c in range(col_cnt):
                for r in range(row_cnt):
                    x = sx + c * col_gap
                    y = sy + r * cell_h
                    points.append((int(x), int(y)))
        else:
            # 행 우선 (→↓): row0의 col0~N → row1의 col0~N → ...
            for r in range(row_cnt):
                for c in range(col_cnt):
                    x = sx + c * col_gap
                    y = sy + r * cell_h
                    points.append((int(x), int(y)))

        return points, None

    # ──────────────────────────────────────────
    # 시작
    # ──────────────────────────────────────────
    def _start(self):
        if self.sending:
            self.log("[경고] 이미 실행 중입니다.")
            return

        self._collect_preset()
        self._save_config()

        points, err = self._compute_points()
        if err:
            self.after(0, lambda: messagebox.showwarning("설정 오류", err))
            return
        if not points:
            self.after(0, lambda: messagebox.showwarning("오류", "좌표가 없습니다."))
            return

        message = self._build_message()

        self._cancel_ev.clear()
        self.sending = True
        self._set_status("⏳ 실행 중…")
        self.log(f"[시작] 좌표 {len(points)}개 | 메시지 {len(message)}자")

        preset = self._active_preset().copy()
        worker = FloatingWorker(preset, self._cancel_ev, self.log)
        self._worker = worker

        def _run():
            try:
                worker.run(points, message)
            finally:
                self.sending = False
                self._set_status("준비됨")

        threading.Thread(target=_run, daemon=True).start()

    # ──────────────────────────────────────────
    # 정지
    # ──────────────────────────────────────────
    def _stop(self):
        self._cancel_ev.set()
        if self._worker:
            self._worker.stop()
        self.sending = False
        self._set_status("⛔ 정지됨")
        self.log("[정지] 사용자 정지 요청")

    # ──────────────────────────────────────────
    # 좌표 테스트 (클릭만)
    # ──────────────────────────────────────────
    def _test_clicks(self):
        if self.sending:
            self.log("[경고] 실행 중에는 테스트 불가")
            return

        self._collect_preset()
        points, err = self._compute_points()
        if err:
            self.after(0, lambda: messagebox.showwarning("설정 오류", err))
            return

        self.log(f"[테스트] {len(points)}개 좌표 클릭 시작 (3초 후)")
        time.sleep(3)
        for i, (x, y) in enumerate(points, 1):
            self.log(f"  [{i}/{len(points)}] 클릭 ({x}, {y})")
            pyautogui.moveTo(x, y, duration=0.05)
            pyautogui.click()
            time.sleep(0.15)
        self.log("[테스트] 완료")

    # ──────────────────────────────────────────
    # 메시지 빌드 (치환 없음)
    # ──────────────────────────────────────────
    def _build_message(self):
        """메시지 텍스트 반환 — 계정 치환 없음"""
        return self.msg_text.get("1.0", "end").strip()

    # ──────────────────────────────────────────
    # 종료
    # ──────────────────────────────────────────
    def _on_close(self):
        self._stop()
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self._collect_preset()
        self._save_config()
        self.destroy()



# ============================================================
# main() 진입점
# ============================================================



def main():
    # ── 로그인 인증 ──────────────────────────
    login = LoginDialog(SHEET_URL)
    authenticated, username = login.show()
    if not authenticated:
        return

    # ── 메인 앱 실행 ─────────────────────────
    app = KakaoApp()
    app.mainloop()


if __name__ == "__main__":
    main()

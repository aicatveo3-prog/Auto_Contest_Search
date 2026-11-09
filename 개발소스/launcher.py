import json
import os
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox, scrolledtext

FROZEN = getattr(sys, "frozen", False)
BASE_DIR = (
    os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
)
PORT = 8765
DASH_MARKER = "AI 공모전 파인더"


def url_for(port):
    return f"http://127.0.0.1:{port}/"
BATCH_FILE = Path(BASE_DIR) / "data" / "exports" / "batch_auto.json"
LABELS_FILE = Path(BASE_DIR) / "data" / "exports" / "labels_auto.json"
ANALYZE_PROMPT = (
    "AGENTS.md 규칙에 따라 data/exports/batch_auto.json 의 items 전체를 분석하고, "
    "결과를 data/exports/labels_auto.json 로 저장해줘. "
    "파일 쓰기 외 다른 작업은 하지 마세요."
)

BG = "#0e1016"
CARD = "#1a1f2c"
CARD_HOVER = "#242b3d"
CARD_LINE = "#272e42"
ACCENT = "#ffd479"
ACCENT_HOVER = "#ffe08d"
TITLE_FG = "#f4f5fa"
BODY_FG = "#a7adc8"
SUB_FG = "#7b819c"
LOG_BG = "#10131b"

SETTINGS_ARG = []

if FROZEN:
    import src.config as contest_config

    contest_config.PROJECT_ROOT = Path(BASE_DIR)
    meipass = getattr(sys, "_MEIPASS", None)
    bundled = Path(meipass) / "config" / "settings.yaml" if meipass else None
    settings_path = (
        bundled
        if bundled and bundled.exists()
        else Path(BASE_DIR) / "config" / "settings.yaml"
    )
    contest_config.DEFAULT_SETTINGS = settings_path
    SETTINGS_ARG = ["--settings", str(settings_path)]

if FROZEN:
    import src.cli as contest_cli
else:
    try:
        import src.cli as contest_cli
    except ImportError:
        contest_cli = None

UPDATE_CMDS = [
    ["-m", "src.cli", "collect", "--modes", "ing", "--cats", "10,20,21,1,26"],
    ["-m", "src.cli", "fetch"],
    ["-m", "src.cli", "enrich"],
    ["-m", "src.cli", "html"],
]
UPDATE_CLI = [
    ["collect", "--modes", "ing", "--cats", "10,20,21,1,26"],
    ["fetch"],
    ["enrich"],
    ["html"],
]


class QueueWriter:
    def __init__(self, line_queue):
        self.line_queue = line_queue

    def write(self, text):
        self.line_queue.put(("line", text))

    def flush(self):
        pass


def cli_python():
    for name in ("py", "python"):
        try:
            subprocess.run([name, "--version"], capture_output=True, timeout=10, check=True)
            return name
        except Exception:
            continue
    return None


def port_open(port=PORT):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def is_our_dashboard(port):
    try:
        no_proxy_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with no_proxy_opener.open(url_for(port), timeout=2) as resp:
            body = resp.read(8192).decode("utf-8", "replace")
        return DASH_MARKER in body
    except Exception:
        return False


def find_free_port(start=PORT, count=10):
    for port in range(start, start + count):
        if not port_open(port):
            return port
    return None


class Card(tk.Frame):
    def __init__(self, parent, title, desc, command, accent=False):
        self.bg = ACCENT if accent else CARD
        self.bg_hover = ACCENT_HOVER if accent else CARD_HOVER
        self.fg = "#181510" if accent else TITLE_FG
        self.sub_fg = "#5d4f1e" if accent else SUB_FG
        super().__init__(
            parent,
            bg=self.bg,
            padx=18,
            pady=13,
            highlightthickness=1,
            highlightbackground=ACCENT if accent else CARD_LINE,
        )
        self.command = command
        self.accent = accent
        self.title_label = tk.Label(
            self, text=title, font=("맑은 고딕", 12, "bold"), bg=self.bg, fg=self.fg
        )
        self.title_label.pack(anchor="w")
        self.desc_label = tk.Label(
            self, text=desc, font=("맑은 고딕", 9), bg=self.bg, fg=self.sub_fg
        )
        self.desc_label.pack(anchor="w", pady=(2, 0))
        for widget in (self, self.title_label, self.desc_label):
            widget.bind("<Button-1>", self._click)
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)

    def _click(self, _event):
        try:
            self.configure(cursor="arrow")
        except Exception:
            pass
        self.command()

    def _enter(self, _event):
        for widget in (self, self.title_label, self.desc_label):
            widget.configure(bg=self.bg_hover, cursor="hand2")

    def _leave(self, _event):
        for widget in (self, self.title_label, self.desc_label):
            widget.configure(bg=self.bg, cursor="arrow")


class App:
    def __init__(self, root):
        self.root = root
        root.title("AI 공모전 검색")
        root.configure(bg=BG)
        root.geometry("480x560")
        root.minsize(420, 480)

        self.line_queue = queue.Queue()
        self.proc = None
        self._busy = False

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=28, pady=(26, 4))
        tk.Label(
            header,
            text="AI 공모전 검색",
            font=("맑은 고딕", 17, "bold"),
            bg=BG,
            fg=TITLE_FG,
        ).pack(anchor="w")
        tk.Label(
            header,
            text="위비티 공모전을 수집하고 AI로 만들 수 있는 공모전을 찾아줍니다",
            font=("맑은 고딕", 9),
            bg=BG,
            fg=SUB_FG,
        ).pack(anchor="w", pady=(3, 0))

        cards = tk.Frame(root, bg=BG)
        cards.pack(fill="x", padx=28, pady=(16, 0))

        self.card_run = Card(
            cards,
            "대시보드 실행",
            "브라우저에서 검색 · ★북마크",
            self.on_dashboard,
            accent=True,
        )
        self.card_run.pack(fill="x", pady=(0, 12))

        self.card_update = Card(
            cards, "데이터 갱신", "최신 공모전 재수집 · 몇 분 소요", self.on_update
        )
        self.card_update.pack(fill="x", pady=(0, 12))

        self.card_analyze = Card(
            cards, "AI 정밀 판정", "에이전트가 본문을 읽고 분류 · 몇 분 소요", self.on_analyze
        )
        self.card_analyze.pack(fill="x")

        self.log = scrolledtext.ScrolledText(
            root,
            height=8,
            font=("Consolas", 9),
            state="disabled",
            bg=LOG_BG,
            fg=BODY_FG,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=CARD_LINE,
            padx=12,
            pady=8,
        )
        self.log.pack(fill="both", expand=True, padx=28, pady=(16, 0))

        self.status = tk.Label(
            root,
            text=self.db_status_text("준비 완료"),
            font=("맑은 고딕", 9),
            bg=BG,
            fg=SUB_FG,
            anchor="w",
        )
        self.status.pack(fill="x", padx=28, pady=(10, 14))

        sys.stdout = QueueWriter(self.line_queue)
        sys.stderr = QueueWriter(self.line_queue)

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(100, self.poll)

    @staticmethod
    def db_status_text(base):
        if (Path(BASE_DIR) / "data" / "contests.db").exists():
            return base + "  ·  기존 데이터 있음"
        return base + "  ·  데이터 없음 — 먼저 ③ 데이터 갱신"

    def log_write(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_busy(self, value):
        self._busy = value

    def poll(self):
        try:
            while True:
                kind, payload = self.line_queue.get_nowait()
                if kind == "line":
                    self.log_write(payload.rstrip("\n"))
                elif kind == "status":
                    self.status.configure(text=payload)
                elif kind == "done":
                    self.set_busy(False)
                    self.status.configure(text=self.db_status_text(payload))
                elif kind == "open":
                    webbrowser.open(url_for(payload or PORT))
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def on_update(self):
        if self._busy:
            return
        self.set_busy(True)
        if FROZEN:
            threading.Thread(
                target=self.cli_tasks_worker,
                args=(UPDATE_CLI, "데이터 갱신 중... (몇 분 소요)", "갱신 완료! 대시보드에서 확인하세요."),
                daemon=True,
            ).start()
        else:
            threading.Thread(
                target=self.subprocess_tasks_worker,
                args=(UPDATE_CMDS, "데이터 갱신 중... (몇 분 소요)", "갱신 완료! 대시보드에서 확인하세요."),
                daemon=True,
            ).start()

    def on_analyze(self):
        if self._busy:
            return
        if contest_cli is None:
            self.status.configure(text="소스 폴더가 필요합니다 (개발소스 경로 확인)")
            return
        self.set_busy(True)
        threading.Thread(target=self.analyze_worker, daemon=True).start()

    def analyze_worker(self):
        opencode = shutil.which("opencode")
        if opencode is None:
            self.queue_put(("done", "opencode 없음 — 정밀 판정은 opencode가 설치된 PC에서만 가능"))
            return
        self.queue_put(("status", "판정 대상 내보내는 중..."))
        try:
            code = contest_cli.main(SETTINGS_ARG + [
                "batch", "--n", "30", "--scope", "either", "--out", "batch_auto.json",
            ])
        except Exception as exc:
            self.queue_put(("done", f"배치 생성 실패: {exc}"))
            return
        if code != 0:
            self.queue_put(("done", "배치 생성 실패 — 로그 확인"))
            return
        try:
            payload = json.loads(BATCH_FILE.read_text(encoding="utf-8"))
            count = len(payload.get("items") or [])
        except Exception:
            count = 0
        if not count:
            self.queue_put(("done", "새로 판정할 공모전이 없습니다 — 먼저 데이터 갱신을 눌러주세요."))
            return
        self.queue_put(("line", f"배치 {count}건 → 에이전트 분석 시작 (몇 분 소요)..."))
        self.queue_put(("status", "AI 정밀 판정 중... 아래 로그에 진행 상황이 표시됩니다"))
        try:
            if LABELS_FILE.exists():
                LABELS_FILE.unlink()
            process = subprocess.Popen(
                [opencode, "run", "--dir", BASE_DIR, ANALYZE_PROMPT],
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as exc:
            self.queue_put(("line", f"에이전트 실행 실패: {exc}"))
            self.queue_put(("done", "실행 실패"))
            return
        threading.Thread(target=self.stream_output, args=(process,), daemon=True).start()
        code = process.wait()
        if code != 0:
            self.queue_put(("done", f"에이전트 종료 코드 {code} — 로그 확인"))
            return
        if not LABELS_FILE.exists():
            self.queue_put(("done", "에이전트가 라벨 파일을 만들지 못했습니다 — 로그 확인"))
            return
        self.queue_put(("status", "판정 결과 적용 중..."))
        try:
            apply_code = contest_cli.main(SETTINGS_ARG + ["apply", str(LABELS_FILE)])
        except Exception as exc:
            self.queue_put(("done", f"적용 실패: {exc}"))
            return
        if apply_code != 0:
            self.queue_put(("done", "적용 실패 — 로그 확인"))
            return
        contest_cli.main(SETTINGS_ARG + ["html"])
        self.queue_put(("done", "정밀 판정 완료! 대시보드에서 확인하세요."))

    def on_dashboard(self):
        if self._busy:
            return
        for port in range(PORT, PORT + 10):
            if is_our_dashboard(port):
                webbrowser.open(url_for(port))
                self.status.configure(text=f"대시보드가 이미 실행 중입니다 (포트 {port}). 브라우저를 열었습니다.")
                return
        port = PORT
        if port_open(PORT):
            port = find_free_port(PORT + 1)
            if port is None:
                messagebox.showerror(
                    "오류", "8765~8774 포트가 모두 다른 프로그램에 의해 사용 중입니다.\n"
                    "해당 프로그램을 종료한 뒤 다시 시도해주세요."
                )
                return
            self.log_write(
                f"! {PORT} 포트를 다른 프로그램이 사용 중 — {port} 포트로 대시보드를 시작합니다."
            )
        if FROZEN:
            threading.Thread(target=self.cli_dashboard_worker, args=(port,), daemon=True).start()
            return
        python = cli_python()
        if python is None:
            messagebox.showerror(
                "오류", "Python이 설치되어 있지 않습니다.\npython.org 에서 설치해주세요."
            )
            return
        threading.Thread(target=self.subprocess_dashboard_worker, args=(port,), daemon=True).start()

    def cli_tasks_worker(self, cli_args, status_text, done_text):
        try:
            for argv in cli_args:
                self.queue_put(("line", "> " + " ".join(argv)))
                self.queue_put(("status", status_text))
                code = contest_cli.main(SETTINGS_ARG + argv)
                if code != 0:
                    self.queue_put(("done", "작업 실패 — 로그를 확인해주세요."))
                    return
        except Exception as exc:
            self.queue_put(("line", f"오류: {exc}"))
            self.queue_put(("done", "작업 실패"))
            return
        self.queue_put(("done", done_text))

    def cli_dashboard_worker(self, port=PORT):
        self.queue_put(("status", f"대시보드 서버 시작 중... (포트 {port})"))
        try:
            contest_cli.main(SETTINGS_ARG + ["serve", "--port", str(port)])
        except OSError:
            self.queue_put(("done", "포트 사용 중 — 이미 실행 중일 수 있습니다."))
            return
        except Exception as exc:
            self.queue_put(("line", f"오류: {exc}"))
            self.queue_put(("done", "서버 시작 실패"))
            return
        self.queue_put(("done", "서버 종료됨"))

    def subprocess_tasks_worker(self, cmds, status_text, done_text):
        python = cli_python()
        if python is None:
            self.queue_put(("done", "Python 필요 — python.org 에서 설치해주세요."))
            return
        for cmd in cmds:
            self.queue_put(("line", "> " + " ".join([python] + cmd)))
            self.queue_put(("status", status_text))
            try:
                process = subprocess.Popen(
                    [python] + cmd,
                    cwd=BASE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
            except Exception as exc:
                self.queue_put(("line", f"실행 실패: {exc}"))
                self.queue_put(("done", "실행 실패"))
                return
            threading.Thread(target=self.stream_output, args=(process,), daemon=True).start()
            code = process.wait()
            if code != 0:
                self.queue_put(("line", f"명령 실패 (종료 코드 {code})"))
                self.queue_put(("done", "작업 실패 — 로그를 확인해주세요."))
                return
        self.queue_put(("done", done_text))

    def subprocess_dashboard_worker(self, port=PORT):
        python = cli_python()
        if python is None:
            self.queue_put(("done", "Python 필요 — python.org 에서 설치해주세요."))
            return
        self.queue_put(("status", f"대시보드 서버 시작 중... (포트 {port})"))
        try:
            self.proc = subprocess.Popen(
                [python, "-m", "src.cli", "serve", "--port", str(port)],
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as exc:
            self.queue_put(("line", f"실행 실패: {exc}"))
            self.queue_put(("done", "실행 실패"))
            return
        threading.Thread(target=self.stream_output, args=(self.proc,), daemon=True).start()
        for _ in range(60):
            if is_our_dashboard(port):
                self.queue_put(("open", port))
                self.queue_put(("status", f"대시보드 실행 중 (포트 {port}) — 브라우저에서 사용하세요."))
                return
            if self.proc.poll() is not None:
                self.queue_put(("line", "서버가 종료되었습니다. 로그를 확인해주세요."))
                self.queue_put(("done", "서버 시작 실패"))
                return
            time.sleep(0.5)
        self.queue_put(("line", "서버 시작이 지연되고 있습니다. 직접 " + url_for(port) + " 을 열어보세요."))
        self.queue_put(("status", "서버 응답 대기 중"))

    def queue_put(self, item):
        self.line_queue.put(item)

    def stream_output(self, process):
        try:
            for line in process.stdout:
                self.queue_put(("line", line))
        except Exception:
            pass

    def on_close(self):
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

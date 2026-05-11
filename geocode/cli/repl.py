"""
交互式 TUI/REPL — YaeLocus 终端界面

当 yaelocus 无参数运行时进入此模式。
借鉴 DeepSeek-TUI: 消息类型系统、多行 Composer、滚动管理、Toast 通知、富状态栏。
"""

import json
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, List, Literal, Optional, Tuple

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel

from rich.text import Text
from rich import box

from .. import __version__
from ..config import Config, OutputPaths, PROJECT_DIR
from .theme import (
    PRIMARY, SUCCESS, WARNING, ERROR, MUTED, DIM,
    USER_COLOR, AI_COLOR, SYS_COLOR, ERR_COLOR, TOOL_COLOR,
    MSG_PREFIX, TOAST_STYLES, SPINNER_FRAMES, STREAMING_PULSE,
)
from .completions import match_command, get_completions, get_inline_suggestion
from .file_picker import MapFilePicker

_console = Console(force_terminal=True)

# ── 跨平台键盘输入 ──────────────────────────────────────────────

_g_reader = None  # singleton KeyboardReader per session

class KeyboardReader:
    """跨平台原始键盘输入读取器 (无外部依赖)"""

    def __init__(self):
        if sys.platform == "win32":
            import msvcrt
            self._getch = msvcrt.getwch
        else:
            self._fd = None
            self._old_settings = None

    def _setup_unix(self):
        import tty, termios
        self._fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setraw(self._fd)

    def _restore_unix(self):
        import termios
        if self._fd is not None and self._old_settings is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)

    def get_key(self) -> str:
        """读取一个键，返回:
         - 单字符 (如 'a', '1', '\n')
         - 控制序列 (如 'ctrl+c', 'up', 'down', 'tab', 'esc', 'pageup', 'pagedown', etc.)
        """
        if sys.platform == "win32":
            return self._get_key_windows()
        else:
            return self._get_key_unix()

    def _get_key_windows(self) -> str:
        import msvcrt, re
        ch = msvcrt.getwch()
        if ch == '\x03': return 'ctrl+c'
        if ch == '\x0c': return 'ctrl+l'
        if ch == '\r': return 'enter'
        if ch == '\n': return 'enter'
        if ch == '\t': return 'tab'
        if ch == '\x08': return 'backspace'
        if ch == '\x7f': return 'backspace'
        # Windows 扩展键前缀 (getwch 对方向键等返回 \xe0 + scancode)
        if ch == '\xe0':
            if msvcrt.kbhit():
                s = msvcrt.getwch()
                return { 'H': 'up', 'P': 'down', 'K': 'left', 'M': 'right',
                         'G': 'home', 'O': 'end', 'I': 'pageup', 'Q': 'pagedown',
                         'S': 'delete', 'R': 'insert' }.get(s, ch + s)
            return 'esc'
        # 部分终端 (\x00 前缀表示 Alt+key 或扩展键)
        if ch == '\x00':
            if msvcrt.kbhit():
                s = msvcrt.getwch()
                return { 'H': 'up', 'P': 'down', 'K': 'left', 'M': 'right',
                         'G': 'home', 'O': 'end', 'I': 'pageup', 'Q': 'pagedown',
                         'S': 'delete' }.get(s, ch + s)
            return 'esc'
        if ch == '\x1b':
            # Unix-style 转义序列 (Windows Terminal / ConEmu / tmux 等终端模拟器)
            time.sleep(0.06)
            if not msvcrt.kbhit():
                return 'esc'
            rest = ''
            while msvcrt.kbhit():
                rest += msvcrt.getwch()

            m = re.match(r'^\[(A|B|C|D)$', rest)
            if m:
                return {'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left'}[m.group(1)]
            m = re.match(r'^\[(H|F)$', rest)
            if m:
                return {'H': 'home', 'F': 'end'}[m.group(1)]
            m = re.match(r'^\[(\d+)~$', rest)
            if m:
                return {'5': 'pageup', '6': 'pagedown', '3': 'delete', '2': 'insert',
                        '1': 'home', '7': 'home', '4': 'end', '8': 'end'}.get(m.group(1), 'esc')
            m = re.match(r'^\[<(\d+);\d+;\d+[Mm]$', rest)
            if m:
                btn = int(m.group(1))
                if btn == 64: return 'scroll_up'
                if btn == 65: return 'scroll_down'
            m = re.match(r'^\[1;(\d+)([ABCD])$', rest)
            if m:
                return {'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left'}.get(m.group(2), 'esc')
            m = re.match(r'^\[M(.)(.)(.)$', rest)
            if m:
                btn = ord(m.group(1))
                if btn in (64, 96): return 'scroll_up'
                if btn in (65, 97): return 'scroll_down'
            m = re.match(r'^O(A|B|C|D)$', rest)
            if m:
                return {'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left'}[m.group(1)]
            m = re.match(r'^O([HFPQRS])$', rest)
            if m:
                return {'H': 'home', 'F': 'end', 'P': 'f1', 'Q': 'f2',
                        'R': 'f3', 'S': 'f4'}.get(m.group(1), 'esc')
            return 'esc'

        return ch

    def _get_key_unix(self) -> str:
        import os as _os, select, re
        self._setup_unix()
        try:
            ch = sys.stdin.read(1)
            if ch == '\x03': return 'ctrl+c'
            if ch == '\x04': return 'ctrl+d'
            if ch == '\x0c': return 'ctrl+l'
            if ch in ('\r', '\n'): return 'enter'
            if ch == '\t': return 'tab'
            if ch in ('\x08', '\x7f'): return 'backspace'
            if ch == '\x1b':
                # 批量读取转义序列（select 10ms 帧间超时）
                rest = ''
                while select.select([sys.stdin], [], [], 0.01)[0]:
                    rest += sys.stdin.read(1)
                if not rest:
                    return 'esc'

                # ── 标准方向键 ──
                if rest in ('[A', '[B', '[C', '[D'):
                    return {'[A': 'up', '[B': 'down', '[C': 'right', '[D': 'left'}[rest]
                if rest in ('[H', '[F'):
                    return {'[H': 'home', '[F': 'end'}[rest]

                # ── N~ 序列: ESC [ N ~ ──
                m = re.match(r'^\[(\d+)~$', rest)
                if m:
                    return {'5': 'pageup', '6': 'pagedown', '3': 'delete', '2': 'insert',
                            '1': 'home', '7': 'home', '4': 'end', '8': 'end'}.get(m.group(1), 'esc')

                # ── SGR 鼠标 ──
                m = re.match(r'^\[<(\d+);\d+;\d+[Mm]$', rest)
                if m:
                    btn = int(m.group(1))
                    if btn == 64: return 'scroll_up'
                    if btn == 65: return 'scroll_down'
                    return 'esc'

                # ── Alt+方向键 ──
                m = re.match(r'^\[1;(\d+)([ABCD])$', rest)
                if m:
                    return {'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left'}.get(m.group(2), 'esc')

                # ── SS3 ──
                if rest in ('OA', 'OB', 'OC', 'OD'):
                    return {'OA': 'up', 'OB': 'down', 'OC': 'right', 'OD': 'left'}[rest]

                # ── 其他 ──
                if len(rest) == 1 and rest.isalpha():
                    return 'alt+' + rest.lower()
                return 'esc'
            return ch
        finally:
            self._restore_unix()


# ── 消息数据模型 ──────────────────────────────────────────────

@dataclass
class Message:
    """TUI 中的一条消息"""
    role: Literal["user", "assistant", "system", "error", "tool"]
    content: str
    timestamp: float = field(default_factory=time.time)
    streaming: bool = False
    markup: bool = False  # True = 内容含 Rich markup 需解析
    tool_name: str = ""
    tool_phase: str = ""  # "running" | "done" | "error"

    @property
    def prefix(self) -> tuple[str, str]:
        return MSG_PREFIX.get(self.role, (" ", "dim"))

    @property
    def rich_lines(self) -> list[Text]:
        """渲染为 Rich Text 行列表"""
        prefix_char, prefix_style = self.prefix
        lines = []
        for i, line_text in enumerate(self.content.split('\n')):
            # markup=True: parse Rich tags. markup=False: plain text (no parsing).
            body = Text.from_markup(line_text) if self.markup and line_text else Text(line_text if line_text else " ")
            if i == 0:
                if self.role == "assistant" and self.streaming:
                    pulse = STREAMING_PULSE[int(time.time() * 2.5) % 2]
                    prefix = Text(f"{pulse} ", style=AI_COLOR)
                elif self.role == "tool" and self.tool_phase == "running":
                    spinner = SPINNER_FRAMES[int(time.time() * 4) % len(SPINNER_FRAMES)]
                    prefix = Text(f"{spinner} ", style=TOOL_COLOR)
                else:
                    prefix = Text(f"{prefix_char} ", style=prefix_style)
                lines.append(prefix + body)
            else:
                lines.append(Text("  ") + body)
        return lines


# ── Toast 管理器 ───────────────────────────────────────────────

class ToastManager:
    """非阻塞 Toast 通知管理器"""

    def __init__(self, max_visible: int = 3):
        self._toasts: list[dict] = []
        self._max = max_visible

    def show(self, msg: str, level: str = "info", ttl: float = 3.0):
        self._toasts.append({"msg": msg, "level": level, "ttl": ttl, "born": time.time()})

    def tick(self, dt: float = 0.1) -> list[dict]:
        now = time.time()
        self._toasts = [t for t in self._toasts if now - t["born"] < t["ttl"]]
        return self._toasts[:self._max]

    @property
    def any_active(self) -> bool:
        self.tick()
        return len(self._toasts) > 0


# ── Composer 状态 ──────────────────────────────────────────────

class Composer:
    """多行输入编辑器状态"""

    def __init__(self):
        self.lines: list[str] = [""]
        self.cursor_line: int = 0
        self.cursor_col: int = 0
        self._history: list[str] = []
        self._history_pos: int = -1  # -1 = 不在历史中
        self._pre_history_text: str = ""  # 进入历史前的内容

    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def is_empty(self) -> bool:
        return len(self.lines) == 1 and self.lines[0] == ""

    def insert(self, ch: str):
        if ch == '\n' or ch == '\r':
            return
        line = self.lines[self.cursor_line]
        self.lines[self.cursor_line] = line[:self.cursor_col] + ch + line[self.cursor_col:]
        self.cursor_col += 1
        self._history_pos = -1

    def newline(self):
        line = self.lines[self.cursor_line]
        before = line[:self.cursor_col]
        after = line[self.cursor_col:]
        self.lines[self.cursor_line] = before
        self.lines.insert(self.cursor_line + 1, after)
        self.cursor_line += 1
        self.cursor_col = 0
        self._history_pos = -1

    def backspace(self):
        if self.cursor_col > 0:
            line = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = line[:self.cursor_col - 1] + line[self.cursor_col:]
            self.cursor_col -= 1
        elif self.cursor_line > 0:
            prev = self.lines[self.cursor_line - 1]
            curr = self.lines[self.cursor_line]
            self.cursor_col = len(prev)
            self.lines[self.cursor_line - 1] = prev + curr
            del self.lines[self.cursor_line]
            self.cursor_line -= 1
        self._history_pos = -1

    def delete(self):
        if self.cursor_col < len(self.lines[self.cursor_line]):
            line = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = line[:self.cursor_col] + line[self.cursor_col + 1:]
        elif self.cursor_line < len(self.lines) - 1:
            curr = self.lines[self.cursor_line]
            nxt = self.lines[self.cursor_line + 1]
            self.lines[self.cursor_line] = curr + nxt
            del self.lines[self.cursor_line + 1]
        self._history_pos = -1

    def move_left(self):
        if self.cursor_col > 0:
            self.cursor_col -= 1
        elif self.cursor_line > 0:
            self.cursor_line -= 1
            self.cursor_col = len(self.lines[self.cursor_line])

    def move_right(self):
        if self.cursor_col < len(self.lines[self.cursor_line]):
            self.cursor_col += 1
        elif self.cursor_line < len(self.lines) - 1:
            self.cursor_line += 1
            self.cursor_col = 0

    def move_home(self):
        self.cursor_col = 0

    def move_end(self):
        self.cursor_col = len(self.lines[self.cursor_line])

    def clear(self):
        self.lines = [""]
        self.cursor_line = 0
        self.cursor_col = 0
        self._history_pos = -1

    def add_to_history(self, text: str):
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
            if len(self._history) > 100:
                self._history.pop(0)
        self._history_pos = -1

    def history_up(self):
        if not self._history:
            return
        if self._history_pos == -1:
            self._pre_history_text = self.text()
            self._history_pos = len(self._history) - 1
        elif self._history_pos > 0:
            self._history_pos -= 1
        self._apply_history()

    def history_down(self):
        if self._history_pos == -1:
            return
        if self._history_pos < len(self._history) - 1:
            self._history_pos += 1
            self._apply_history()
        else:
            self._history_pos = -1
            self._restore_pre_history()

    def _apply_history(self):
        text = self._history[self._history_pos]
        self.lines = text.split('\n')
        self.cursor_line = len(self.lines) - 1
        self.cursor_col = len(self.lines[-1])

    def _restore_pre_history(self):
        self.lines = self._pre_history_text.split('\n')
        self.cursor_line = len(self.lines) - 1
        self.cursor_col = len(self.lines[-1])


# ── REPL 会话 ──────────────────────────────────────────────────

class ReplSession:
    """交互式 REPL 会话 — DeepSeek-TUI 风格"""

    def __init__(self):
        self.messages: list[Message] = []
        self.max_messages = 100
        self.running = True
        self._command_count = 0
        self._ai_active = False
        self._processing = False
        self._live = None

        self.composer = Composer()
        self.toast = ToastManager()
        self.reader = KeyboardReader()

        self._scroll_line = 0
        self._stick_to_bottom = True
        self._inline_suggestion: str = ""  # ghost text
        self._modal: Optional[Any] = None  # modal map picker

        # AI 流式辅助
        self._streaming_msg_idx = -1
        self._ai_client_ref = None

        # Layout — 固定区域尺寸，防止 UI 割裂
        self.layout = Layout()
        self._build_layout()

    def _term_size(self) -> tuple[int, int]:
        """获取当前终端尺寸"""
        try:
            import shutil
            sz = shutil.get_terminal_size()
            return (sz.columns, sz.lines)
        except Exception:
            return (80, 24)

    def _build_layout(self):
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="toast_area", size=1),
            Layout(name="body", ratio=1),
            Layout(name="composer_area", size=3),
            Layout(name="footer", size=1),
        )

    def _update_suggestion(self):
        """更新内联补全 ghost text"""
        self._inline_suggestion = get_inline_suggestion(self.composer.text()) or ""

    # ── 公开入口 ─────────────────────────────────────────────

    def run(self):
        self._welcome()
        self._render_header()
        self._render_body()
        self._render_composer()
        self._render_footer()

        try:
            self._event_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    # ── 事件循环 ─────────────────────────────────────────────

    def _event_loop(self):
        with Live(self.layout, console=_console, refresh_per_second=15, screen=True) as live:
            self._live = live
            while self.running:
                self._refresh_all()
                live.refresh()

                try:
                    key = self.reader.get_key()
                except Exception:
                    time.sleep(0.05)
                    continue

                handled = self._handle_key(key)
                if not handled and isinstance(key, str) and len(key) == 1:
                    self.composer.insert(key)
                self._update_suggestion()

    def _cleanup(self):
        if self._ai_client_ref:
            try:
                self._ai_client_ref.close()
            except Exception:
                pass

    # ── 键盘处理 ─────────────────────────────────────────────

    def _handle_key(self, key: str) -> bool:
        """处理键盘输入。返回 True 表示已处理。"""
        c = self.composer

        # ── 模态模式: 拦截所有按键 ──
        if self._modal is not None:
            result = self._modal.handle_key(key)
            if result == "open":
                opened = self._modal.open_selected()
                if opened and self._modal.selected_file:
                    self.toast.show(f"已打开: {self._modal.selected_file.name}", "success")
                self._modal = None
            elif result == "close":
                self._modal = None
            self._stick_to_bottom = True
            return True

        # ── 编辑操作 ──
        if key == 'enter':
            if c.is_empty and not self.messages:
                return True  # 空输入，忽略
            # 空输入时 g/G 用于滚动
            if c.is_empty:
                text = c.text()
            else:
                self._submit(c.text())
                c.add_to_history(c.text())
                c.clear()
            return True

        if key == 'alt+enter' or key == 'alt+\r':
            c.newline()
            return True

        if key == 'backspace':
            c.backspace()
            return True

        if key == 'delete':
            c.delete()
            return True

        if key == 'left':
            c.move_left()
            return True

        if key == 'right':
            c.move_right()
            return True

        if key == 'home':
            c.move_home()
            return True

        if key == 'end':
            c.move_end()
            return True

        if key in ('up', 'alt+up'):
            c.history_up()
            return True

        if key in ('down', 'alt+down'):
            c.history_down()
            return True

        if key == 'tab':
            self._do_completion()
            return True

        # ── 全局快捷键 ──
        if key == 'ctrl+l':
            self.messages.clear()
            self._scroll_line = 0
            return True

        if key == 'ctrl+c':
            if self._ai_active:
                self._cancel_ai()
                return True
            else:
                self.running = False
                return True

        if key == 'esc':
            if not c.is_empty:
                c.clear()
            return True

        if key == 'scroll_up':
            self._scroll_line = max(0, self._scroll_line - 3)
            self._stick_to_bottom = False
            return True

        if key == 'scroll_down':
            self._scroll_line += 3
            self._stick_to_bottom = False
            return True

        if key == 'pageup':
            _, term_h = self._term_size()
            self._scroll_line = max(0, self._scroll_line - max(5, term_h // 2))
            self._stick_to_bottom = False
            return True

        if key == 'pagedown':
            _, term_h = self._term_size()
            self._scroll_line += max(5, term_h // 2)
            self._stick_to_bottom = False
            return True

        if key == 'g':
            self._scroll_line = 0
            self._stick_to_bottom = False
            return True

        if key == 'G':
            self._stick_to_bottom = True
            self._scroll_line = 0
            return True

        # ── / 快捷打开斜杠菜单 ──
        if key == '/' and c.is_empty:
            c.insert('/')
            return True

        return False  # 未处理，交给字符插入

    # ── 自然语言→命令匹配 ────────────────────────────────

    def _match_nl(self, text: str) -> Optional[Tuple[str, List[str]]]:
        """检测自然语言输入是否可映射为命令。返回 (cmd_hint, args) 或 None。"""
        import re as _re
        data_files = "|".join(
            f.name for f in (PROJECT_DIR / "data").glob("*")
            if f.suffix.lower() in (".xlsx", ".xls", ".csv")
        ) if (PROJECT_DIR / "data").exists() else ""

        patterns: list[tuple[str, str, str]] = [
            # (正则, 组名, 命令模板)
            (r"处理\s*(?:文件\s*)?(?:data/)?([^\s]+\.(?:xlsx|xls|csv))", "file",
             "geocode batch -i data/{file}"),
            (r"批量\s*(?:处理|编码)\s*(?:文件\s*)?(?:data/)?([^\s]+\.(?:xlsx|xls|csv))?", "file",
             "geocode batch -i data/{file}"),
            (r"(?:帮我\s*)?(?:编码|转换|查询|定位)\s*[：: ]?\s*(.+)", "addr",
             "geocode single {addr}"),
            (r"逆地理(?:编码)?\s*[：: ]?\s*([\d.]+\s*[,，\s]+\s*[\d.]+)", "coords",
             "geocode reverse {coords}"),
            (r"分析\s*(?:data/)?([^\s]+\.(?:xlsx|xls|csv))", "file",
             "ai analyze -i data/{file}"),
            (r"(?:规划|安排)\s*路线\s*(?:data/)?([^\s]+\.(?:xlsx|xls|csv))?", "file",
             "ai route -i data/{file}"),
            (r"(?:生成|做|创建)\s*(?:个?\s*)?地图\s*(?:data/)?([^\s]+\.(?:xlsx|xls|csv))?", "file",
             "map create -i data/{file}"),
            (r"列出\s*(?:data/)?\s*文件", "none", "map list"),
        ]

        for pat, group, template in patterns:
            m = _re.search(pat, text, _re.IGNORECASE)
            if m:
                if group == "none":
                    return (template, [])
                val = m.group(1).strip().strip('"\'')
                if group == "coords":
                    parts = _re.split(r"[,，\s]+", val)
                    if len(parts) >= 2:
                        return ("geocode reverse", [parts[0], parts[1]])
                    return (f"geocode reverse {val}", [])
                if group == "file":
                    return ("geocode batch", ["-i", f"data/{val}"])
                if group == "addr":
                    return ("geocode single", [val])
        return None

    # ── 提交与分发 ─────────────────────────────────────────

    def _submit(self, text: str):
        text = text.strip()
        if not text:
            return

        self._add_message(Message(role="user", content=text))
        self._command_count += 1
        self._stick_to_bottom = True

        # 1. 斜杠命令
        if text.startswith("/"):
            self._handle_slash(text)
            return

        # 2. 已注册命令
        matched = match_command(text)
        if matched:
            group, cmd, args = matched
            self._run_registered_command(group, cmd, args)
            return

        # 3. 自然语言匹配
        nl = self._match_nl(text)
        if nl:
            cmd, args = nl
            parts = cmd.strip().split()
            if len(parts) >= 2:
                # 尝试作为注册命令运行
                nl_matched = match_command(f"{parts[0]} {parts[1]} {' '.join(args)}")
                if nl_matched:
                    self._run_registered_command(*nl_matched)
                    return
            # 未能匹配 → 提示用户
            self._add_message(Message(role="assistant",
                content=f"已理解您的意图。请执行: [cyan]{cmd} {' '.join(args)}[/cyan]"))
            return

        # 4. AI 回退
        self._chat_with_ai(text)

    def _handle_slash(self, text: str):
        cmd = text.lower().strip()
        if cmd in ("/quit", "/q", "/exit"):
            self._add_message(Message(role="system", content="再见！"))
            self.running = False
        elif cmd in ("/help", "/h", "/?"):
            self._show_help()
        elif cmd == "/clear":
            self.messages.clear()
            self._add_message(Message(role="system", content="已清屏"))
        elif cmd == "/status":
            self._show_status()
        elif cmd == "/export":
            self._export_history()
        elif cmd == "/map":
            picker = MapFilePicker()
            count = picker.refresh()
            self._modal = picker
            if count == 0:
                self._add_message(Message(role="system",
                    content="没有找到地图文件。请先运行 geocode batch 或 map create 生成地图。"))
                self._modal = None
        elif cmd.startswith("/geocode "):
            # 快捷地理编码: /geocode <地址>
            addr = text[len("/geocode "):].strip().strip('"\'')
            if addr:
                self._run_registered_command("geocode", "single", [addr])
            else:
                self._add_message(Message(role="error", content="用法: /geocode <地址>"))
        elif cmd.startswith("/config "):
            sub = text[len("/config "):].strip()
            if sub in ("setup", "check", "test-api"):
                self._run_registered_command("config", sub, [])
            else:
                self._add_message(Message(role="error", content="用法: /config setup|check|test-api"))
        elif cmd.startswith("/map "):
            sub = text[len("/map "):].strip()
            if sub == "list":
                self._run_registered_command("map", "list", [])
            else:
                self._add_message(Message(role="error", content="用法: /map list"))
        else:
            self._add_message(Message(role="error",
                content=f"未知命令: {text}\n输入 /help 查看可用命令"))

    def _run_registered_command(self, group: str, cmd: str, args: list[str]):
        if group == "_standalone":
            self._invoke_typer([cmd] + args)
            return
        if group == "_special":
            self._handle_slash(f"/{cmd}")
            return
        self._invoke_typer([group, cmd] + args)

    def _invoke_typer(self, argv: list[str]):
        from .app import app
        self._processing = True
        cmd_name = " ".join(argv[:2]) if len(argv) >= 2 else argv[0] if argv else "?"
        think_msg = Message(role="tool", content=f"⏺ {cmd_name} 执行中...", tool_phase="running")
        self._add_message(think_msg)
        think_idx = len(self.messages) - 1
        # 暂停外层 Live，防止与命令内部的 Rich Progress/Live 冲突
        if self._live:
            self._refresh_all()
            self._live.refresh()
            self._live.stop()

        old_stdout, old_stderr = sys.stdout, sys.stderr
        outp, errp = StringIO(), StringIO()
        # 告诉子命令当前在 TUI 上下文中运行，禁用交互式提示
        os.environ['YAELOCUS_TUI'] = '1'
        try:
            sys.stdout = outp; sys.stderr = errp
            try:
                app(argv, standalone_mode=False)
            except SystemExit:
                pass
            sys.stdout = old_stdout; sys.stderr = old_stderr
            output = outp.getvalue().strip()
            errors = errp.getvalue().strip()
            if think_idx < len(self.messages) and self.messages[think_idx] is think_msg:
                self.messages.pop(think_idx)
            if output:
                self._add_message(Message(role="assistant", content=output))
            if errors:
                self._add_message(Message(role="system", content=errors))
            self.toast.show("命令完成", "success")
        except Exception as e:
            sys.stdout = old_stdout; sys.stderr = old_stderr
            if think_idx < len(self.messages) and self.messages[think_idx] is think_msg:
                self.messages.pop(think_idx)
            self._add_message(Message(role="error",
                content=f"命令执行失败: {e}\n{traceback.format_exc()[-200:]}"))
        finally:
            self._processing = False
            os.environ.pop('YAELOCUS_TUI', None)
            # 恢复外层 Live
            if self._live:
                self._live.start()
                self._refresh_all()
                self._live.refresh()

    # ── AI 对话 (Agent Loop) ─────────────────────────────────

    def _build_context(self) -> list[dict]:
        """从 self.messages 提取最近对话上下文（借鉴 Claude Code 的完整历史模式）"""
        context = []
        for msg in self.messages[-30:]:
            if msg.role == "user" and msg.content:
                context.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant" and msg.content and not msg.streaming:
                context.append({"role": "assistant", "content": msg.content[:800]})
        return context

    def _ai_stream(self, messages: list[dict]) -> str:
        """流式获取 AI 回复并实时显示在 TUI 中。返回完整文本。"""
        think_msg = Message(role="tool", content="⏺ AI 思考中...", tool_phase="running")
        self._add_message(think_msg)
        think_idx = len(self.messages) - 1
        self._refresh_all()
        if self._live:
            self._live.refresh()

        msg = Message(role="assistant", content="", streaming=True)
        self._add_message(msg)
        self._streaming_msg_idx = len(self.messages) - 1
        if think_idx < len(self.messages) and self.messages[think_idx] is think_msg:
            self.messages.pop(think_idx)
            self._streaming_msg_idx -= 1

        full = ""
        last_flush = 0.0
        try:
            for token in self._ai_client_ref.chat_stream(messages=messages, temperature=0.7, max_tokens=2000):
                full += token
                now = time.time()
                if now - last_flush > 0.05:
                    self.messages[self._streaming_msg_idx].content = full
                    if self._live:
                        self._refresh_all()
                        self._live.refresh()
                    last_flush = now
        except Exception:
            resp = self._ai_client_ref.chat(messages=messages, temperature=0.7, max_tokens=2000)
            full = resp["choices"][0]["message"]["content"].strip()
        self.messages[self._streaming_msg_idx].content = full
        self.messages[self._streaming_msg_idx].streaming = False
        return full

    def _execute_cmd(self, cmd: str) -> str:
        """在 TUI 上下文中执行一条命令，返回捕获的输出文本。"""
        from .app import app
        parts = cmd.strip().split()
        if not parts:
            return "(空命令)"
        result_prefix = f"⏺ {cmd[:60]}..."
        think_msg = Message(role="tool", content=result_prefix, tool_phase="running")
        self._add_message(think_msg)
        think_idx = len(self.messages) - 1
        if self._live:
            self._live.stop()

        outp, errp = StringIO(), StringIO()
        old_stdout, old_stderr = sys.stdout, sys.stderr
        os.environ['YAELOCUS_TUI'] = '1'
        try:
            sys.stdout = outp; sys.stderr = errp
            try:
                app(parts, standalone_mode=False)
            except SystemExit:
                pass
            sys.stdout = old_stdout; sys.stderr = old_stderr
            output = outp.getvalue().strip()
            errors = errp.getvalue().strip()
        except Exception as e:
            sys.stdout = old_stdout; sys.stderr = old_stderr
            output = f"错误: {e}"
            errors = ""
        finally:
            os.environ.pop('YAELOCUS_TUI', None)
            if think_idx < len(self.messages) and self.messages[think_idx] is think_msg:
                self.messages.pop(think_idx)
            if self._live:
                self._live.start()
                self._refresh_all()
                self._live.refresh()

        result = output or "(命令已执行)"
        if errors:
            result = f"{result}\n{errors}"
        return result

    def _agent_loop(self, text: str):
        """Agent 主循环（借鉴 Claude Code query.ts: needsFollowUp flag 控制循环）"""
        from ..ai.system_prompt import build_system_prompt
        context = self._build_context()
        messages: list[dict] = [
            {"role": "system", "content": build_system_prompt()},
            *context,
            {"role": "user", "content": text},
        ]
        self._ai_active = True

        try:
            max_rounds = 4
            for round_idx in range(max_rounds):
                full = self._ai_stream(messages)
                if self._live:
                    self._refresh_all()
                    self._live.refresh()

                # 提取 [CMD]...[/CMD] 块（借鉴 query.ts: filter tool_use blocks）
                cmd_blocks = re.findall(r'\[CMD\]\s*\n?(.*?)\n?\s*\[/CMD\]', full, re.DOTALL | re.IGNORECASE)
                if not cmd_blocks:
                    break  # needsFollowUp = false → 退出循环

                # 执行命令并收集结果（借鉴 query.ts: tool_result 以 user role 注入）
                results = []
                for i, cmd in enumerate(cmd_blocks):
                    cmd = cmd.strip()
                    if not cmd:
                        continue
                    self._add_message(Message(role="system", content=f"执行: [cyan]{cmd}[/cyan]", markup=True))
                    self._refresh_all()
                    if self._live:
                        self._live.refresh()
                    result_text = self._execute_cmd(cmd)
                    results.append((i + 1, result_text))

                if not results:
                    break

                combined = "\n".join(
                    f"[命令执行结果 {idx}]:\n{r}" for idx, r in results
                )
                messages.append({"role": "assistant", "content": full})
                messages.append({"role": "user", "content": combined})
        finally:
            self._ai_active = False
            if self._ai_client_ref:
                try: self._ai_client_ref.close()
                except Exception: pass
                self._ai_client_ref = None

    def _chat_with_ai(self, text: str):
        """AI 对话入口：检查配置 → 创建客户端 → 进入 Agent Loop"""
        if not Config.AI_ENABLED:
            self._add_message(Message(role="error",
                content="AI 未启用。运行 config setup 配置。\n输入 /help 查看可用命令"))
            return
        try:
            from ..ai import AIClient
            self._ai_client_ref = AIClient()
            self._agent_loop(text)
        except Exception as e:
            self._add_message(Message(role="error", content=f"AI 调用失败: {e}"))
            self._ai_active = False

    def _cancel_ai(self):
        self._ai_active = False
        if self._streaming_msg_idx >= 0 and self._streaming_msg_idx < len(self.messages):
            msg = self.messages[self._streaming_msg_idx]
            msg.streaming = False
            if not msg.content:
                msg.content = "[已取消]"
                msg.role = "system"
        if self._ai_client_ref:
            try: self._ai_client_ref.close()
            except Exception: pass
            self._ai_client_ref = None
        self.toast.show("AI 请求已取消", "warning")

    # ── 自动补全 ────────────────────────────────────────────

    def _do_completion(self):
        # 若有 ghost suggestion 且光标在行尾，Tab 接受 suggestion
        c = self.composer
        if self._inline_suggestion and c.cursor_col == len(c.lines[c.cursor_line]):
            for ch in self._inline_suggestion:
                c.insert(ch)
            self._inline_suggestion = ""
            self._update_suggestion()
            return

        text = c.text().strip()
        completions = get_completions(text)
        if not completions:
            return
        if len(completions) == 1:
            parts = text.split()
            if parts:
                if text.endswith(" "):
                    self.composer.insert(completions[0].strip())
                else:
                    parts[-1] = completions[0].strip()
                    new_text = " ".join(parts)
                    self.composer.clear()
                    for line in new_text.split('\n'):
                        for ch in line:
                            self.composer.insert(ch)
                        if '\n' in new_text:
                            self.composer.newline()
            return
        # 多个补全 → 显示在系统中
        self._add_message(Message(role="system", markup=True, content="  ".join(f"[dim]{c.strip()}[/dim]" for c in completions[:12])))

    # ── 消息管理 ────────────────────────────────────────────

    def _add_message(self, msg: Message):
        self.messages.append(msg)
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

    def _refresh_all(self):
        """刷新所有 Layout 区域"""
        self._update_toast()
        self._render_header()
        self._render_body()
        self._render_composer()
        self._render_footer()

    # ── 渲染 ─────────────────────────────────────────────────

    def _welcome(self):
        self._add_message(Message(role="system", markup=True,
            content=f"YaeLocus [bold]{__version__}[/bold] 交互式终端\n"
                    "输入命令或自然语言，/help 查看帮助，Ctrl+C 退出"))
        if not Config.validate():
            self._add_message(Message(role="system", markup=True,
                content="[yellow]未配置 API 密钥。运行 config setup 配置[/yellow]"))

    def _render_header(self):
        header_text = Text.assemble(
            (f"YaeLocus ", "bold #1a73e8"),
            (f"v{__version__}", "dim"),
            ("     ", ""),
            ("/help", "dim"), (" 帮助  ", ""),
            ("/quit", "dim"), (" 退出  ", ""),
            ("/clear", "dim"), (" 清屏  ", ""),
            ("/status", "dim"), (" 状态", ""),
        )
        self.layout["header"].update(Panel(
            header_text, border_style="#1a73e8", box=box.HORIZONTALS, padding=(0, 2)))

    def _render_body(self):
        # ── 模态模式: 渲染选择器 ──
        if self._modal is not None:
            _, term_h = self._term_size()
            avail_h = max(5, term_h - 9)
            rendered = self._modal.render(avail_h)
            from rich.console import Group
            self.layout["body"].update(Panel(
                Group(*rendered), box=box.HORIZONTALS, padding=(0, 1)))
            return

        rendered_lines: list[Text] = []
        for msg in self.messages:
            rendered_lines.extend(msg.rich_lines)
            rendered_lines.append(Text(""))  # 消息间距

        if not rendered_lines:
            rendered_lines = [Text("", style=DIM)]

        from rich.console import Group
        # 动态计算可用高度: 终端高度 - header(3) - composer(3) - footer(1) - padding
        _, term_h = self._term_size()
        avail_h = max(5, term_h - 9)

        total = len(rendered_lines)
        if self._stick_to_bottom or total <= avail_h:
            visible = rendered_lines[-avail_h:]
        else:
            start = max(0, min(self._scroll_line, total - avail_h))
            visible = rendered_lines[start:start + avail_h]
            remaining = total - (start + avail_h)
            if remaining > 0:
                visible.append(Text(f"  [↑ 更早的消息 ({remaining} 行)]", style=DIM))

        self.layout["body"].update(Panel(
            Group(*visible), box=box.HORIZONTALS, padding=(0, 1)))

    def _render_composer(self):
        # ── 模态模式: 显示操作提示 ──
        if self._modal is not None:
            msg = Text("  方向键选择 | Enter 打开 | Esc 返回", style="dim")
            from rich.console import Group
            self.layout["composer_area"].update(Panel(
                Group(msg, Text(""), Text("")),
                border_style="#1a73e8", padding=(0, 2)))
            return

        c = self.composer
        cursor_line = c.cursor_line
        cursor_col = c.cursor_col

        # 提示符: 处理中 → ⏺, 待机 → ›
        if self._processing or self._ai_active:
            prompt_char = "⏺"
            prompt_style = "bold #f39c12"
        else:
            prompt_char = "›"
            prompt_style = "bold #6aaef2"

        # 最多显示 3 行: 优先显示光标所在行
        total_lines = len(c.lines)
        vis_start = max(0, min(cursor_line - 1, total_lines - 3))
        vis_end = min(total_lines, vis_start + 3)
        vis_lines = c.lines[vis_start:vis_end]

        composer_lines = []
        for vi, i in enumerate(range(vis_start, vis_end)):
            line_text = vis_lines[vi]
            safe = line_text.replace("[", "[[")
            is_cursor = (i == cursor_line)

            if is_cursor:
                col = min(cursor_col, len(safe))
                before = Text.from_markup(safe[:col]) if safe[:col] else Text("")
                cursor = Text(" ", style="reverse")
                after = Text.from_markup(safe[col:]) if safe[col:] else Text("")
                body_parts = [before, cursor, after]
                # Ghost text inline suggestion (光标在行尾时显示)
                if self._inline_suggestion and col == len(safe):
                    ghost = Text(self._inline_suggestion, style="dim italic")
                    body_parts.append(ghost)
                body = Text.assemble(*body_parts)
            else:
                body = Text.from_markup(safe) if safe else Text(" ")

            if i == 0:
                line = Text.assemble((f"{prompt_char} ", prompt_style), body)
            else:
                line = Text.assemble(("  ", ""), body)
            composer_lines.append(line)

        # 补齐到正好 3 行
        while len(composer_lines) < 3:
            composer_lines.append(Text(""))

        from rich.console import Group
        self.layout["composer_area"].update(Panel(
            Group(*composer_lines[:3]),
            border_style=prompt_style.replace("bold ", ""), padding=(0, 2)))

    def _render_footer(self):
        # ── 模态模式: 显示地图浏览器标识 ──
        if self._modal is not None:
            self.layout["footer"].update(Panel(
                "[#1a73e8]地图浏览器[/] [dim]| Esc 返回 |[/]",
                box=box.HORIZONTALS, padding=(0, 2)))
            return

        apis = Config.get_available_apis()
        api_parts = []
        for a in ["amap", "tianditu", "baidu"]:
            if a in apis:
                api_parts.append(f"[{SUCCESS}]● {a}[/]")
            else:
                api_parts.append(f"[{MUTED}]○ {a}[/]")

        cache_info = ""
        cache_path = OutputPaths.DATABASE / "geocache.db"
        if cache_path.exists():
            try:
                from ..cache import CacheManager
                cm = CacheManager(str(cache_path))
                stats = cm.get_stats()
                cm.close()
                cache_info = (f" | [{SUCCESS}]{stats['total_entries']}[/]条 "
                            f"([{SUCCESS}]{stats['hit_rate']}%[/])")
            except Exception:
                pass

        if self._processing:
            mode = "[#f39c12]⏺ 处理中[/]"
        elif self._ai_active:
            mode = "[#f39c12]⏺ AI[/]"
        else:
            mode = "[dim]待机[/]"

        self.layout["footer"].update(Panel(
            f"[dim]API:[/] {' '.join(api_parts)}{cache_info} | {mode} "
            f"[dim]| 命令: {self._command_count} | Ctrl+C 退出[/]",
            box=box.HORIZONTALS, padding=(0, 2)))

    def _update_toast(self):
        toasts = self.toast.tick()
        if toasts and toasts[0]:
            t = toasts[0]
            icon, color = TOAST_STYLES.get(t["level"], TOAST_STYLES["info"])
            line = Text.from_markup(f"  {icon} [{MUTED}]{t['msg']}[/]")
            self.layout["toast_area"].update(Panel(line, box=box.HORIZONTALS, padding=(0, 1)))
        else:
            self.layout["toast_area"].update(Panel("", box=box.HORIZONTALS))

    def _toast(self, msg: str, level: str = "info"):
        self.toast.show(msg, level)

    # ── 帮助 ─────────────────────────────────────────────────

    def _show_help(self):
        lines = []
        w1, w2, w3 = 32, 18, 36
        sep = f"+{'-'*(w1+2)}+{'-'*(w2+2)}+{'-'*(w3+2)}+"
        header = f"| {'命令':<{w1}} | {'说明':<{w2}} | {'示例':<{w3}} |"
        lines.append(f"[bold #1a73e8]可用命令[/]"); lines.append("")
        lines.append(f"[dim]{sep}[/]")
        lines.append(f"[bold cyan]{header}[/]")
        lines.append(f"[dim]{sep}[/]")
        for name, desc, ex in [
            ("geocode single <地址>", "单地址转坐标", 'geocode single "北京"'),
            ("geocode batch -i <文件>", "批量地理编码", "geocode batch -i data/清单.xlsx"),
            ("geocode reverse <lat> <lon>", "经纬度转地址", "geocode reverse 39.9 116.4"),
            ("map list", "列出可处理文件", "map list --detail"),
            ("map create -i <文件>", "生成地图", "map create -i output/结果.csv"),
            ("ai chat <消息>", "AI 对话", "ai chat 分析这些地址"),
            ("ai route -i <文件>", "AI 路线规划", "ai route -i output/结果.csv"),
            ("config setup", "配置 API 密钥", "config setup"),
            ("config check", "环境诊断", "config check"),
            ("config cache stats", "缓存统计", "config cache stats --json"),
        ]:
            lines.append(f"[cyan]{name:<{w1}}[/] [dim]|[/] {desc:<{w2}} [dim]|[/] [dim]{ex:<{w3}}[/]")
        lines.append(f"[dim]{sep}[/]")
        lines.append("")
        for name, desc, ex in [
            ("/geocode <地址>", "快捷地理编码", "/geocode 北京"),
            ("/help", "显示帮助", "/help"),
            ("/clear", "清屏", "/clear"),
            ("/status", "状态信息", "/status"),
            ("/quit", "退出", "/quit"),
        ]:
            lines.append(f"[cyan]{name:<{w1}}[/] [dim]|[/] {desc:<{w2}} [dim]|[/] [dim]{ex:<{w3}}[/]")
        lines.append("")
        lines.append(f"[dim]直接输入自然语言可进入 AI 对话模式[/]")
        self._add_message(Message(role="assistant", markup=True, content="\n".join(lines)))

    def _show_status(self):
        info = []
        apis = Config.get_available_apis()
        info.append(f"API: {', '.join(apis) if apis else '无'}")
        info.append(f"AI 启用: {'是' if Config.AI_ENABLED else '否'} ({Config.AI_PROVIDER})")
        cache_path = OutputPaths.DATABASE / "geocache.db"
        if cache_path.exists():
            try:
                from ..cache import CacheManager
                cm = CacheManager(str(cache_path))
                stats = cm.get_stats()
                cm.close()
                info.append(f"缓存: {stats['total_entries']} 条 (命中率 {stats['hit_rate']}%)")
            except Exception:
                info.append("缓存: 无法读取")
        info.append(f"会话命令: {self._command_count}")
        info.append(f"消息数: {len(self.messages)}")
        self._add_message(Message(role="assistant", content="\n".join(info)))

    def _export_history(self):
        path = OutputPaths.EXPORT / "session_history.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"YaeLocus v{__version__} 会话", time.strftime("%Y-%m-%d %H:%M:%S"), "=" * 50, ""]
        for m in self.messages:
            lines.append(f"[{m.role}] {m.content[:200]}")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        self._add_message(Message(role="system", content=f"已导出到 {path}"))
        self._toast("会话已导出", "success")

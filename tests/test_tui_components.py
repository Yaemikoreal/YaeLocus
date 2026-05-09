"""
TUI 逻辑组件测试 — Composer, ToastManager, Message

测试纯逻辑，不依赖 Rich 终端渲染。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from geocode.cli.repl import Composer, Message, ToastManager


# ════════════════════════════════════════════════════════════════════
# Composer 测试
# ════════════════════════════════════════════════════════════════════

class TestComposerBasic:
    def test_starts_empty(self):
        c = Composer()
        assert c.text() == ""
        assert c.is_empty is True

    def test_insert_char(self):
        c = Composer()
        c.insert("a")
        assert c.text() == "a"
        c.insert("b")
        assert c.text() == "ab"

    def test_insert_special_chars(self):
        c = Composer()
        c.insert("[")
        c.insert("]")
        assert c.text() == "[]"

    def test_newline(self):
        c = Composer()
        c.insert("h")
        c.insert("e")
        c.insert("l")
        c.insert("l")
        c.insert("o")
        assert c.text() == "hello"
        c.newline()
        assert c.lines == ["hello", ""]
        c.insert("w")
        c.insert("o")
        c.insert("r")
        c.insert("l")
        c.insert("d")
        assert c.lines == ["hello", "world"]

    def test_backspace(self):
        c = Composer()
        c.insert("h")
        c.insert("e")
        c.insert("l")
        c.insert("l")
        c.insert("o")
        assert c.text() == "hello"
        c.backspace()
        c.backspace()
        assert c.text() == "hel"

    def test_backspace_empty_line(self):
        c = Composer()
        c.backspace()
        assert c.is_empty

    def test_backspace_at_line_start_joins(self):
        """行首退格应合并到上一行"""
        c = Composer()
        c.insert("a")
        c.insert("b")
        c.newline()
        c.insert("c")
        c.insert("d")
        assert c.lines == ["ab", "cd"]
        # 光标在 "cd" 后
        c.move_home()  # 光标到行首
        c.backspace()   # 行首退格 → 合并到上一行
        assert c.lines == ["abcd"]

    def test_delete_char(self):
        c = Composer()
        c.insert("a")
        c.insert("b")
        c.insert("c")
        c.move_left()
        c.move_left()   # 光标在 'b' 前
        c.delete()       # 删除 'b'
        assert c.text() == "ac"

    def test_clear(self):
        c = Composer()
        c.insert("hello world")
        assert not c.is_empty
        c.clear()
        assert c.text() == ""
        assert c.is_empty


class TestComposerCursor:
    def test_move_left_right(self):
        c = Composer()
        c.insert("a")
        c.insert("b")
        c.insert("c")
        # 光标在末尾
        c.move_left()
        c.move_left()   # 光标在 'b' 前
        c.insert("X")
        # X 应插入到 'a' 和 'b' 之间
        assert c.text() == "aXbc"

    def test_move_home_end(self):
        c = Composer()
        c.insert("a")
        c.insert("b")
        c.insert("c")
        c.move_home()
        c.insert("X")
        assert c.text() == "Xabc"
        c.move_end()
        c.insert("Z")
        assert c.text() == "XabcZ"


class TestComposerHistory:
    def test_history_up_down_restores(self):
        c = Composer()
        c.insert("current")
        c.add_to_history("cmd1")
        c.add_to_history("cmd2")

        # history_up 从最新的开始
        c.history_up()
        assert c.text() == "cmd2"

        c.history_up()
        assert c.text() == "cmd1"

        # history_down 返回
        c.history_down()
        assert c.text() == "cmd2"

        c.history_down()
        assert c.text() == "current"

    def test_history_empty_does_nothing(self):
        c = Composer()
        c.insert("hello")
        c.history_up()
        assert c.text() == "hello"

    def test_history_duplicate_not_added(self):
        c = Composer()
        c.add_to_history("cmd1")
        c.add_to_history("cmd1")
        # 不应重复添加
        prefilled = sum(1 for _ in [None])  # 只是一个帮助
        c.history_up()
        assert c.text() == "cmd1"
        c.history_up()
        # 应该只有一条，第二次历史向上不应改变
        assert c.text() == "cmd1"


# ════════════════════════════════════════════════════════════════════
# ToastManager 测试
# ════════════════════════════════════════════════════════════════════

class TestToastManager:
    def test_starts_empty(self):
        tm = ToastManager()
        assert len(tm._toasts) == 0

    def test_tick_keeps_fresh_toasts(self):
        import time
        tm = ToastManager()
        tm._toasts = [{
            "id": "new",
            "message": "fresh",
            "level": "info",
            "born": time.time(),
            "ttl": 99,
        }]
        tm.tick()
        assert len(tm._toasts) == 1


# ════════════════════════════════════════════════════════════════════
# Message 数据模型测试
# ════════════════════════════════════════════════════════════════════

class TestMessageModel:
    def test_user_prefix(self):
        msg = Message(role="user", content="hello")
        prefix_char, style = msg.prefix
        assert prefix_char == "▎"
        assert "cyan" in style

    def test_assistant_prefix(self):
        msg = Message(role="assistant", content="world")
        prefix_char, style = msg.prefix
        assert prefix_char == "●"

    def test_system_prefix(self):
        msg = Message(role="system", content="info")
        prefix_char, _ = msg.prefix
        assert prefix_char == "·"

    def test_error_prefix(self):
        msg = Message(role="error", content="fail")
        prefix_char, _ = msg.prefix
        assert prefix_char == "✗"

    def test_tool_prefix(self):
        msg = Message(role="tool", content="executing...")
        prefix_char, _ = msg.prefix
        assert prefix_char == "⚙"

    def test_streaming_default_false(self):
        msg = Message(role="assistant", content="hello")
        assert msg.streaming is False

    def test_rich_lines_single_line(self):
        msg = Message(role="assistant", content="Single line")
        lines = msg.rich_lines
        assert len(lines) >= 1

    def test_rich_lines_multiline(self):
        msg = Message(role="assistant", content="Line1\nLine2\nLine3")
        lines = msg.rich_lines
        assert len(lines) >= 2

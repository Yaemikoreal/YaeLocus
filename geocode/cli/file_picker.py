"""
模态文件选择器 — 浏览已生成的地图 HTML 文件

方向键上下选择，Enter 在浏览器中打开，Esc 关闭。
"""

import webbrowser
from pathlib import Path
from typing import Optional

from rich.text import Text

from ..config import OutputPaths


class MapFilePicker:
    """模态覆盖层：浏览 output/map/ 中的 HTML 文件"""

    def __init__(self):
        self.files: list[Path] = []
        self.selected_index: int = 0

    def refresh(self) -> int:
        """扫描 output/map/ 目录。返回找到的文件数。"""
        map_dir = OutputPaths.MAP
        if map_dir.exists():
            self.files = sorted(
                map_dir.glob("*.html"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
        else:
            self.files = []
        self.selected_index = 0 if self.files else -1
        return len(self.files)

    @property
    def is_empty(self) -> bool:
        return len(self.files) == 0

    @property
    def selected_file(self) -> Optional[Path]:
        if 0 <= self.selected_index < len(self.files):
            return self.files[self.selected_index]
        return None

    def handle_key(self, key: str) -> Optional[str]:
        """处理模态模式中的按键事件。

        Returns:
            "open"  — 调用方应在浏览器中打开所选文件
            "close" — 调用方应关闭模态
            None    — 按键已被消费，无需其他操作
        """
        if key in ("up", "alt+up", "scroll_up"):
            if self.files:
                self.selected_index = max(0, self.selected_index - 1)
            return None
        if key in ("down", "alt+down", "scroll_down"):
            if self.files:
                self.selected_index = min(len(self.files) - 1, self.selected_index + 1)
            return None
        if key == "enter":
            return "open"
        if key == "esc":
            return "close"
        return None

    def render(self, avail_height: int) -> list[Text]:
        """渲染文件列表为 Rich Text 行列表。"""
        if not self.files:
            return [Text("  (暂无地图文件 — 请先运行 geocode batch 或 map create)", style="dim")]

        lines: list[Text] = [
            Text("  [ 地图文件浏览器 ]", style="bold #1a73e8"),
            Text("  方向键: 上下选择 | Enter: 打开 | Esc: 返回", style="dim"),
            Text(""),
        ]

        start = max(0, min(self.selected_index - 5, len(self.files) - avail_height + 6))
        end = min(len(self.files), start + max(10, avail_height - 6))
        if start > 0:
            lines.append(Text(f"    ↑ {start} 个文件...", style="dim"))

        for i in range(start, end):
            f = self.files[i]
            size_kb = f.stat().st_size / 1024
            if i == self.selected_index:
                line = Text(f"  > {f.name}  ({size_kb:.0f} KB)", style="bold reverse #1a73e8")
            else:
                line = Text(f"    {f.name}  ({size_kb:.0f} KB)")
            lines.append(line)

        if end < len(self.files):
            lines.append(Text(f"    ↓ {len(self.files) - end} 个文件...", style="dim"))

        lines.append(Text(""))
        if self.selected_file:
            lines.append(Text(f"  选择: {self.selected_file}", style="dim"))

        return lines

    def open_selected(self) -> bool:
        """在默认浏览器中打开当前选中的文件。"""
        if self.selected_file and self.selected_file.exists():
            webbrowser.open(str(self.selected_file.absolute()))
            return True
        return False

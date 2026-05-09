"""
支持 python -m geocode 直接运行

[DEPRECATED] 请使用 yaelocus 命令代替。
"""

import sys


def _warn_and_redirect():
    """打印弃用提示并重定向到 Typer CLI"""
    print("[DEPRECATED] python -m geocode 已弃用，请改用 yaelocus", file=sys.stderr)
    print("  yaelocus geocode batch -i data/file.xlsx   # 批量地理编码", file=sys.stderr)
    print("  yaelocus geocode single \"地址\"             # 单个地址", file=sys.stderr)
    print("  yaelocus                                   # 交互式终端", file=sys.stderr)
    print("", file=sys.stderr)

    # Redirect to Typer CLI
    from geocode.cli.app import app
    app()


if __name__ == "__main__":
    _warn_and_redirect()

"""
统一 Agent Loop — Claude Code 设计模式

从 AI 调用到工具执行再到错误恢复，全部在此统一处理。
所有前端 (Web GUI / Ink TUI / Rich TUI) 共享此逻辑。

SSE 事件类型:
  content       — AI 文本内容 token
  reasoning     — 思维链 token
  tool_use      — 工具调用完成 (结构化: id + name + arguments)
  tool_use_delta — 工具调用增量 (流式参数)
  tool_result   — 工具执行结果
  tool_error    — 工具执行错误 (含 recoverable + auto_fix_action)
  round_start   — 新一轮 Agent Loop 开始
  done          — 全部完成

混合协议策略:
  1. 优先使用 tools 参数让模型原生输出 tool_use 块
  2. 如果模型不支持或返回纯文本 [CMD] 块，fallback 到正则提取
  3. 两者均支持 ERROR_RECOVERY_MAP 自动恢复
"""

import json
import logging
import os
import re
import shlex
import sys
from io import StringIO
from typing import Callable, Dict, Iterator, List, Optional

from ..agent.errors import ERROR_RECOVERY_MAP, get_agent_error
from .client import AIClient, AIClientError
from .system_prompt import build_system_prompt
from .tools import CMD_PATTERN, MAX_AGENT_ROUNDS, YAELOCUS_TOOLS
from ..chat import ChatManager

logger = logging.getLogger(__name__)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

INTERACTIVE_COMMAND_PREFIXES = [
    "ai route ",
    "yaelocus ai route ",
    "config setup",
    "yaelocus config setup",
]


def _execute_command_sync(cmd: str, timeout: int = 120) -> Dict:
    """同步执行 CLI 命令并返回结构化结果

    Args:
        cmd: yaelocus 命令字符串
        timeout: 超时秒数

    Returns:
        dict 包含 command, exit_code, stdout, stderr, success, parsed
    """
    cmd_lower = cmd.lower()
    for prefix in INTERACTIVE_COMMAND_PREFIXES:
        if cmd_lower.startswith(prefix) and "--headless" not in cmd_lower:
            return {
                "command": cmd,
                "exit_code": 1,
                "stdout": "",
                "stderr": (
                    f"命令 '{cmd.split()[0]} {cmd.split()[1] if len(cmd.split()) > 1 else ''}' "
                    "需要交互式输入，请使用对应的 Web API。"
                ),
                "success": False,
                "parsed": None,
            }

    old_stdout, old_stderr = sys.stdout, sys.stderr
    captured_out, captured_err = StringIO(), StringIO()
    sys.stdout, sys.stderr = captured_out, captured_err
    os.environ["YAELOCUS_TUI"] = "1"
    exit_code = 0
    try:
        from ..cli.app import app as typer_app

        # 预处理 Windows 路径：将反斜杠转为正斜杠
        # shlex.split() 是 POSIX 解析器，反斜杠会被解释为转义字符
        cmd_normalized = re.sub(r'\\+', '/', cmd)
        argv = shlex.split(cmd_normalized)
        typer_app(argv, standalone_mode=False)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception as e:
        exit_code = 1
        captured_err.write(str(e))
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr

    raw_out = captured_out.getvalue()
    raw_err = captured_err.getvalue()
    clean_out = _ANSI_RE.sub("", raw_out)
    clean_out = re.sub(
        r"[─━│┃┄┅┆┇┈┉┊┋┌┍┎┏┐┑┒┓└┕┖┗┘┙┚┛├┝┞┟┠┡┢┣┤┥┦┧┨┩┪┫┬┭┮┯╰╱╲╳╴┵┶┷╸╹╺┻┼┽┾┿╀╁╂╃╄╅╆╇╈╉╊╋╌╍╎╏═║╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬╭╮╯╰]",
        "",
        clean_out,
    )
    clean_err = _ANSI_RE.sub("", raw_err)

    parsed = None
    if clean_out.strip():
        try:
            parsed = json.loads(clean_out.strip())
        except (json.JSONDecodeError, ValueError):
            pass

    return {
        "command": cmd,
        "exit_code": exit_code,
        "stdout": clean_out.strip(),
        "stderr": clean_err.strip(),
        "success": exit_code == 0,
        "parsed": parsed,
    }


def _parse_error_from_result(result: Dict) -> Optional[Dict]:
    """从命令执行结果中解析结构化错误

    优先检查 parsed JSON 中的 error/status 字段，
    fallback 检查 stderr 中的关键词。
    """
    parsed = result.get("parsed")
    if parsed and isinstance(parsed, dict):
        if parsed.get("status") == "error" and parsed.get("error"):
            err = parsed["error"]
            if isinstance(err, dict):
                return err
            return {"code": "unknown", "message": str(err)}
        if parsed.get("error"):
            err = parsed["error"]
            if isinstance(err, dict):
                return err
            return {"code": "unknown", "message": str(err)}

    stderr = result.get("stderr", "")
    if not result.get("success") and stderr:
        for keyword, code in [
            ("NO_API_KEY", "NO_API_KEY"),
            ("API_QUOTA_EXCEEDED", "API_QUOTA_EXCEEDED"),
            ("INVALID_API_KEY", "INVALID_API_KEY"),
            ("FILE_NOT_FOUND", "FILE_NOT_FOUND"),
            ("COLUMN_NOT_FOUND", "COLUMN_NOT_FOUND"),
            ("NETWORK_ERROR", "NETWORK_ERROR"),
        ]:
            if keyword in stderr:
                return {"code": code, "message": stderr[:200]}

    return None


class AgentLoop:
    """统一 Agent Loop

    Usage:
        loop = AgentLoop(client=my_ai_client)
        for event in loop.run(prompt="分析 data/清单.xlsx"):
            # event 是 dict, event["type"] 区分事件类型
            print(event)
    """

    def __init__(
        self,
        client: AIClient,
        chat_manager: Optional[ChatManager] = None,
        max_rounds: int = MAX_AGENT_ROUNDS,
        use_tools: bool = True,
    ):
        self.client = client
        self.chat_manager = chat_manager
        self.max_rounds = max_rounds
        self.use_tools = use_tools
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(
        self,
        prompt: str,
        context: Optional[List[Dict]] = None,
        session_id: Optional[str] = None,
        on_event: Optional[Callable[[Dict], None]] = None,
    ) -> Iterator[Dict]:
        """执行完整 Agent Loop，yield 事件字典

        Args:
            prompt: 用户输入
            context: 前置对话上下文 [{role, content}]
            session_id: 会话 ID (用于持久化)
            on_event: 同步事件回调 (可选，用于非迭代场景)

        Yields:
            事件字典，event["type"] 区分类型:
            content, reasoning, tool_use, tool_use_delta, tool_result,
            tool_error, round_start, done
        """
        self._cancelled = False

        if context is None:
            context = []

        if session_id and self.chat_manager:
            context = self.chat_manager.build_context(session_id)
            self.chat_manager.add_message(session_id, "user", prompt)

        system_prompt = build_system_prompt()
        messages: List[Dict] = [
            {"role": "system", "content": system_prompt},
            *context,
            {"role": "user", "content": prompt},
        ]

        current_prompt = prompt

        for round_idx in range(self.max_rounds):
            if self._cancelled:
                break

            yield {"type": "round_start", "round": round_idx + 1, "max_rounds": self.max_rounds}
            if on_event:
                on_event({"type": "round_start", "round": round_idx + 1, "max_rounds": self.max_rounds})

            full_content = ""
            full_reasoning = ""
            tool_calls: List[Dict] = []
            cmd_blocks: List[str] = []
            tools_param = YAELOCUS_TOOLS if self.use_tools else None

            try:
                for chunk in self.client.chat_stream(
                    messages, temperature=0.7, tools=tools_param
                ):
                    if self._cancelled:
                        break

                    chunk_type = chunk.get("type", "")

                    if chunk_type == "content":
                        full_content += chunk.get("content", "")
                        yield chunk
                        if on_event:
                            on_event(chunk)

                    elif chunk_type == "reasoning":
                        full_reasoning += chunk.get("content", "")
                        yield chunk
                        if on_event:
                            on_event(chunk)

                    elif chunk_type == "tool_use":
                        tool_calls.append({
                            "id": chunk.get("id", ""),
                            "name": chunk.get("name", ""),
                            "arguments": chunk.get("arguments", ""),
                        })
                        yield chunk
                        if on_event:
                            on_event(chunk)

                    elif chunk_type == "tool_use_delta":
                        yield chunk
                        if on_event:
                            on_event(chunk)

            except AIClientError as e:
                yield {
                    "type": "error",
                    "code": e.code,
                    "message": str(e),
                }
                if on_event:
                    on_event({"type": "error", "code": e.code, "message": str(e)})
                break

            except Exception as e:
                yield {
                    "type": "error",
                    "code": "unknown",
                    "message": str(e),
                }
                if on_event:
                    on_event({"type": "error", "code": "unknown", "message": str(e)})
                break

            # Fallback: 从文本内容中提取 [CMD] 块
            if not tool_calls and full_content:
                cmd_regex = re.compile(CMD_PATTERN, re.DOTALL | re.IGNORECASE)
                visible_content = cmd_regex.sub(
                    lambda m: "" if m.group(1).strip() and (cmd_blocks.append(m.group(1).strip()) or True) else "",
                    full_content,
                ).strip()
                full_content = visible_content or full_content
            elif tool_calls:
                for tc in tool_calls:
                    try:
                        args = json.loads(tc.get("arguments", "{}"))
                        cmd = args.get("command", "")
                        if cmd:
                            cmd_blocks.append(cmd)
                    except json.JSONDecodeError:
                        pass

            # 保存助手消息到后端会话
            if session_id and self.chat_manager:
                self.chat_manager.add_message(
                    session_id, "assistant", full_content, reasoning=full_reasoning
                )

            # 无工具调用 → 完成
            if not cmd_blocks:
                break

            # 执行工具调用 → 自动恢复循环
            tool_results_text = ""
            for cmd in cmd_blocks:
                if self._cancelled:
                    break

                yield {
                    "type": "tool_result",
                    "command": cmd,
                    "status": "running",
                }
                if on_event:
                    on_event({"type": "tool_result", "command": cmd, "status": "running"})

                result = _execute_command_sync(cmd)
                result_text = result.get("stdout", "") or result.get("stderr", "")
                success = result.get("success", False)

                # 尝试解析错误并自动恢复
                error_info = _parse_error_from_result(result) if not success else None
                if error_info:
                    error_code = error_info.get("code", "unknown")
                    recovery = get_agent_error(error_code)

                    yield {
                        "type": "tool_error",
                        "command": cmd,
                        "error": error_info,
                        "recoverable": recovery.recoverable if recovery else False,
                        "auto_fix_action": recovery.auto_fix_action if recovery else None,
                    }
                    if on_event:
                        on_event({
                            "type": "tool_error",
                            "command": cmd,
                            "error": error_info,
                            "recoverable": recovery.recoverable if recovery else False,
                            "auto_fix_action": recovery.auto_fix_action if recovery else None,
                        })

                    # 自动恢复: 执行修复命令后重试原始命令
                    if recovery and recovery.recoverable and recovery.auto_fix_action:
                        yield {
                            "type": "tool_recovery",
                            "original_command": cmd,
                            "fix_command": recovery.auto_fix_action,
                        }
                        if on_event:
                            on_event({
                                "type": "tool_recovery",
                                "original_command": cmd,
                                "fix_command": recovery.auto_fix_action,
                            })

                        fix_result = _execute_command_sync(recovery.auto_fix_action)
                        if fix_result.get("success"):
                            # 重试原始命令
                            result = _execute_command_sync(cmd)
                            result_text = result.get("stdout", "") or result.get("stderr", "")
                            success = result.get("success", False)
                    elif recovery and recovery.recoverable and recovery.retry_after_seconds:
                        import time as _time
                        yield {
                            "type": "tool_recovery",
                            "original_command": cmd,
                            "wait_seconds": recovery.retry_after_seconds,
                        }
                        _time.sleep(min(recovery.retry_after_seconds, 5))
                        result = _execute_command_sync(cmd)
                        result_text = result.get("stdout", "") or result.get("stderr", "")
                        success = result.get("success", False)

                yield {
                    "type": "tool_result",
                    "command": cmd,
                    "result": result_text,
                    "success": success,
                    "parsed": result.get("parsed"),
                    "exit_code": result.get("exit_code", 0),
                }
                if on_event:
                    on_event({
                        "type": "tool_result",
                        "command": cmd,
                        "result": result_text,
                        "success": success,
                    })

                # 截断过长结果（阈值增加到 10000，避免关键信息截断）
                if len(result_text) > 10000:
                    result_text = result_text[:10000] + "\n...（结果已截断）"
                tool_results_text += f"命令: {cmd}\n结果: {result_text}\n\n"

            if not tool_results_text:
                break

            # 注入工具结果，继续循环
            messages.append({"role": "assistant", "content": full_content})
            messages.append({"role": "user", "content": tool_results_text})
            current_prompt = "请基于以上命令执行结果继续分析。如果已经得到最终答案，请直接给出结论。"

            if session_id and self.chat_manager:
                self.chat_manager.add_message(
                    session_id, "user", tool_results_text
                )

        yield {"type": "done"}
        if on_event:
            on_event({"type": "done"})
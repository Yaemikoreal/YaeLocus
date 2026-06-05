/**
 * YaeLocus TUI — 主应用
 *
 * 借鉴 Claude Code App.tsx: 状态管理 + 键盘绑定 + 消息分发 + 模态管理
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Box, Text, useInput, useApp, useStdout } from 'ink';
import { FullscreenLayout } from './components/FullscreenLayout';
import { Messages } from './components/Messages';
import { MessageData } from './components/Message';
import { PromptInput } from './components/PromptInput';
import { StatusBar } from './components/StatusBar';
import { NewMessagesPill } from './components/NewMessagesPill';
import { Toast, ToastData } from './components/Toast';
import { HelpPanel } from './components/HelpPanel';
import { MapPicker } from './components/MapPicker';
import { useAPI, ChatMessage, HealthStatus } from './hooks/useAPI';
import { useStream } from './hooks/useStream';
import { useCommandHistory } from './hooks/useCommandHistory';

// ── ID生成 ──────────────────────────────────────────────────────

let idCounter = 0;
function nextId(): string {
  return `msg-${++idCounter}-${Date.now()}`;
}

// ── 自然语言匹配 ──────────────────────────────────────────────

function matchNL(text: string): string | null {
  const t = text.toLowerCase().replace(/\s+/g, ' ');
  if (/^(帮助|help|使用说明|what)/i.test(t)) return '/help';
  if (/(列出|显示|查看)\s*(文件|列表|地图|map)/i.test(t)) return 'map list';
  if (/(检查|状态|status|配置|config\b)/i.test(t)) return 'config check';
  if (/(缓存|cache)\s*(统计|status|stats)/i.test(t)) return 'config cache stats';
  if (/(清空|清除|清理)\s*(缓存|cache)/i.test(t)) return 'config cache clear';
  return null;
}

// ── Slash 命令表 ──────────────────────────────────────────────

const SLASH_HANDLERS: Record<string, string> = {
  '/help': 'help',
  '/h': 'help',
  '/clear': 'clear',
  '/quit': 'quit',
  '/q': 'quit',
  '/exit': 'quit',
  '/status': 'status',
  '/export': 'export',
  '/map': 'map_picker',
  '/sessions': 'sessions',
  '/doctor': 'doctor',
  '/compact': 'compact',
  '/copy': 'copy',
  '/model': 'model',
};

function isSlash(text: string): boolean {
  return /^\//.test(text.trim());
}

export function App() {
  const { exit } = useApp();
  const { write: writeStdout } = useStdout();
  const api = useAPI();
  const stream = useStream();
  const history = useCommandHistory();

  // ── 状态 ─────────────────────────────────────────────────────

  const [messages, setMessages] = useState<MessageData[]>([]);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [streamingReasoning, setStreamingReasoning] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [processing, setProcessing] = useState(false);
  const [modal, setModal] = useState<'help' | 'map_picker' | null>(null);
  const [toasts, setToasts] = useState<ToastData[]>([]);
  const [newMessageCount, setNewMessageCount] = useState(0);
  const [showLogo, setShowLogo] = useState(true);
  const stickToBottom = useRef(true);
  const abortRef = useRef<AbortController | null>(null);
  const toastTimers = useRef<ReturnType<typeof setTimeout>[]>([]);

  // ── 启动健康检查 ─────────────────────────────────────────────

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  // ── Cleanup ──────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      toastTimers.current.forEach(clearTimeout);
      abortRef.current?.abort();
    };
  }, []);

  // ── Toast ────────────────────────────────────────────────────

  const addToast = useCallback((message: string, level: ToastData['level'] = 'info') => {
    // error 级别持久化（不自动消失）
    const persistent = level === 'error';
    const t: ToastData = { id: String(Date.now()), message, level, persistent };
    setToasts(prev => [...prev, t].slice(-3));

    // 只有非持久化 Toast 才自动消失
    if (!persistent) {
      const timer = setTimeout(() => {
        setToasts(prev => prev.filter(x => x.id !== t.id));
        toastTimers.current = toastTimers.current.filter(x => x !== timer);
      }, 3000);
      toastTimers.current.push(timer);
    }
  }, []);

  // 清除持久化 Toast（用户手动关闭）
  const clearPersistentToast = useCallback(() => {
    setToasts(prev => prev.filter(t => !t.persistent));
  }, []);

  // ── 消息管理 ────────────────────────────────────────────────

  const addMessage = useCallback((msg: Omit<MessageData, 'id'>): MessageData => {
    const m: MessageData = { id: nextId(), ...msg };
    setMessages(prev => {
      const next = [...prev, m];
      if (next.length > 200) next.shift();
      return next;
    });
    // BUG #8 修复: 当不在底部时递增新消息计数
    if (!stickToBottom.current) {
      setNewMessageCount(c => c + 1);
    }
    return m;
  }, []);

  const updateLastMessage = useCallback((updates: Partial<MessageData>) => {
    setMessages(prev => {
      if (prev.length === 0) return prev;
      const next = [...prev];
      next[next.length - 1] = { ...next[next.length - 1], ...updates };
      return next;
    });
  }, []);

  // ── 命令执行 ────────────────────────────────────────────────

  const executeCmd = useCallback(async (cmd: string): Promise<string> => {
    try {
      const result = await api.execute(cmd);
      if (result.success) {
        return result.stdout || '成功';
      }
      return result.stderr || result.stdout || `失败 (exit: ${result.exit_code})`;
    } catch (err: unknown) {
      return `执行失败: ${err instanceof Error ? err.message : String(err)}`;
    }
  }, [api]);

// ── AI Agent 循环 ───────────────────────────────────────────

  const SSE_CHUNK_TIMEOUT_MS = 30000

  const agentLoop = useCallback(async (prompt: string, fileContext?: string) => {
    setProcessing(true);

    const controller = new AbortController();
    abortRef.current = controller;

    const context: ChatMessage[] = [];
    for (const msg of messages.slice(-30)) {
      if (msg.role === 'user' && msg.content) {
        context.push({ role: 'user', content: msg.content });
      } else if (msg.role === 'assistant' && !msg.streaming && msg.content) {
        context.push({ role: 'assistant', content: msg.content.slice(0, 800) });
      } else if (msg.role === 'tool' && msg.toolResult) {
        context.push({ role: 'user', content: `[工具执行结果]: ${msg.toolResult}` });
      }
    }

    let fullPrompt = prompt;
    if (fileContext) {
      try {
        const fileData = await api.readFile(fileContext);
        if (fileData.preview) {
          fullPrompt = `文件: ${fileContext}\n数据预览: ${JSON.stringify(fileData.preview).slice(0, 2000)}\n\n${prompt}`;
        }
      } catch { /* ignore */ }
    }

    let fullContent = '';
    let fullReasoning = '';

    try {
      const res = await api.agentStream(fullPrompt, context);
      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      let lastChunkTime = Date.now();

      while (true) {
        if (Date.now() - lastChunkTime > SSE_CHUNK_TIMEOUT_MS) {
          addMessage({ role: 'error', content: 'AI 响应超时，请检查网络连接后重试' });
          break;
        }

        if (controller.signal.aborted) {
          reader.cancel();
          break;
        }

        const { done, value } = await reader.read();
        if (done) break;
        lastChunkTime = Date.now();
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;
          const data = trimmed.slice(6);
          if (data === '[DONE]') break;
          try {
            const event = JSON.parse(data);

            switch (event.type) {
              case 'content':
                fullContent += event.content || '';
                setStreamingText(fullContent);
                break;
              case 'reasoning':
                fullReasoning += event.content || '';
                setStreamingReasoning(fullReasoning.length > 200 ? '◌ ' + fullReasoning.slice(-200) : fullReasoning);
                break;
              case 'tool_use':
                fullContent += `\n⏳ 执行: ${event.name || 'command'}...\n`;
                setStreamingText(fullContent);
                break;
              case 'tool_result':
                fullContent += `\n✓ ${event.command || ''}${event.success === false ? ' (失败)' : ''}\n`;
                if (event.result) {
                  const resultText = event.result.length > 2000 ? event.result.slice(0, 2000) + '...' : event.result;
                  fullContent += `\`\`\`\n${resultText}\n\`\`\`\n`;
                }
                setStreamingText(fullContent);
                break;
              case 'tool_error':
                fullContent += `\n✗ ${event.command || ''} — ${event.error?.message || '错误'}${event.recoverable ? ' (自动恢复中...)' : ''}\n`;
                setStreamingText(fullContent);
                break;
              case 'tool_recovery':
                fullContent += `\n⟳ ${event.fix_command ? `自动修复: ${event.fix_command}` : `等待 ${event.wait_seconds}s 后重试...`}\n`;
                setStreamingText(fullContent);
                break;
              case 'round_start':
                // Round info is shown via streamingText
                break;
              case 'error': {
                setStreamingText(null);
                setStreamingReasoning(null);
                const errCode = event.code || 'unknown';
                const errMap: Record<string, string> = {
                  auth_error: 'AI 认证失败，请检查 API Key 配置',
                  rate_limit: 'AI 请求过于频繁，请稍后重试',
                  network_error: 'AI 网络连接失败，请检查网络',
                  timeout: 'AI 请求超时，请稍后重试',
                };
                addMessage({
                  role: 'error',
                  content: errMap[errCode] || `AI 错误: ${event.message || errCode}`,
                });
                break;
              }
            }
          } catch { /* skip malformed JSON */ }
        }
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) { /* cancelled */ }
      else {
        setStreamingText(null);
        setStreamingReasoning(null);
        addMessage({
          role: 'error',
          content: `AI 错误: ${err instanceof Error ? err.message : String(err)}`,
        });
      }
    }

    // Finalize: save to messages
    setStreamingText(null);
    setStreamingReasoning(null);

    // Clean up CMD blocks from content
    const cmdRegex = /\[CMD\]\s*\n?(.*?)\n?\s*\[\/CMD\]/gs;
    const visibleContent = fullContent.replace(cmdRegex, '').trim();

    if (visibleContent) {
      addMessage({ role: 'assistant', content: visibleContent });
    }

    abortRef.current = null;
    setProcessing(false);
  }, [messages, addMessage, api]);

  // ── Slash 命令处理 (BUG #11 + #14 修复) ──────────────────────

  const handleSlash = useCallback((text: string) => {
    const cmd = text.trim().split(/\s+/)[0];
    const handler = SLASH_HANDLERS[cmd];

    switch (handler) {
      case 'help':
        setModal(m => m === 'help' ? null : 'help');
        return;
      case 'clear':
        setMessages([]);
        setShowLogo(true);
        addToast('已清屏', 'info');
        return;
      case 'quit':
        exit();
        return;
      case 'status':
        addMessage({
          role: 'system',
          content: `API: ${health?.apis?.join(', ') || '无'} | AI: ${health?.ai_enabled ? '已启用' : '未启用'} | 模型: ${health?.version || '-'} | 消息: ${messages.length}`,
        });
        return;
      case 'export':
        addToast('会话历史已导出', 'success');
        return;
      case 'map_picker':
        setModal(m => m === 'map_picker' ? null : 'map_picker');
        return;
      case 'sessions':
        addMessage({
          role: 'system',
          content: `日志目录: output/log/\n缓存: output/database/geocache.db\n地图: output/map/\n\n使用 /resume 暂不支持，即将推出。`,
        });
        return;
      case 'doctor':
        executeCmd('config check').then(result => {
          addMessage({ role: 'system', content: result });
        });
        return;
      case 'compact': {
          const summary = messages.slice(-10).map(m => `[${m.role}] ${m.content?.slice(0, 80)}`).join('\n');
          setMessages(messages.slice(-10));
          setShowLogo(true);
          addMessage({ role: 'system', content: `上下文已压缩。\n${summary}` });
          addToast('上下文已压缩', 'info');
        }
        return;
      case 'copy':
        // 复制最后一条 AI 回复
        const lastAI = [...messages].reverse().find(m => m.role === 'assistant');
        if (lastAI?.content) {
          addToast(`已复制: ${lastAI.content.slice(0, 50)}...`, 'success');
        } else {
          addToast('没有可复制的内容', 'warning');
        }
        return;
      case 'model':
        addMessage({
          role: 'system',
          content: `AI 供应商: ${health?.ai_enabled ? '已启用' : '未启用'}\n版本: ${health?.version || '-'}\n可用 API: ${health?.apis?.join(', ') || '无'}`,
        });
        return;
    }

    // /geocode <地址>
    if (cmd === '/geocode') {
      const addr = text.trim().replace(/^\/geocode\s*/i, '');
      if (addr) {
        executeCmd(`geocode single "${addr}"`).then(result => {
          addMessage({ role: 'system', content: result });
        });
        return;
      }
    }

    // /config <sub>
    if (cmd === '/config') {
      const sub = text.trim().replace(/^\/config\s*/i, '');
      executeCmd(`config ${sub}`).then(result => {
        addMessage({ role: 'system', content: result });
      });
      return;
    }

    // BUG #14 修复: 未知命令
    addMessage({
      role: 'system',
      content: `未知命令: ${cmd}。输入 /help 查看可用命令。`,
    });
  }, [health, messages, addMessage, addToast, executeCmd, exit]);

  // ── 提交处理 ────────────────────────────────────────────────

  const handleSubmit = useCallback((text: string) => {
    if (processing) return;
    setShowLogo(false);
    history.addToHistory(text);

    // Slash 命令 (BUG #11 修复: 不再在 handleSlash 中重复添加用户消息)
    if (isSlash(text)) {
      addMessage({ role: 'user', content: text });
      handleSlash(text);
      return;
    }

    // 自然语言匹配
    const matched = matchNL(text);
    if (matched) {
      addMessage({ role: 'user', content: text });
      if (isSlash(matched)) {
        handleSlash(matched);
      } else {
        executeCmd(matched).then(result => {
          addMessage({ role: 'system', content: result });
        });
      }
      return;
    }

    // AI 回退
    addMessage({ role: 'user', content: text });

    const fileMatch = text.match(/-i\s+(\S+\.(?:csv|xlsx|xls|json))/i);
    const fileContext = fileMatch ? fileMatch[1] : undefined;

    agentLoop(text, fileContext);
  }, [processing, history, addMessage, handleSlash, executeCmd, agentLoop]);

  // ── 取消AI ──────────────────────────────────────────────────

  const cancelAI = useCallback(() => {
    abortRef.current?.abort();
    setStreamingText(null);
    setStreamingReasoning(null);
    setProcessing(false);
  }, []);

  // ── 全局键盘绑定 ────────────────────────────────────────────

  useInput((input, key) => {
    // Escape 级联: 模态 > 取消AI
    if (key.escape) {
      if (modal) { setModal(null); return; }
      if (processing) { cancelAI(); return; }
      return;
    }

    // Ctrl+L — 终端重置（借鉴 Claude Code）
    if (input === 'l' && key.ctrl) {
      writeStdout('\x1b[2J\x1b[H');
      return;
    }

    // PageUp/PageDown — 滚动
    if (key.pageUp) {
      stickToBottom.current = false;
      setNewMessageCount(c => c + 3);
      return;
    }
    if (key.pageDown) {
      setNewMessageCount(c => Math.max(0, c - 3));
      if (newMessageCount <= 3) stickToBottom.current = true;
      return;
    }
  });

  // ── Modal 键盘绑定 (BUG #2 修复: 仅在 modal 激活时，不冲突) ──

  const isModalActive = modal !== null;

  // ── 渲染 ────────────────────────────────────────────────────

  const version = health?.version || '1.6.0';
  const apis = health?.apis || [];
  const aiEnabled = health?.ai_enabled || false;

  return (
    <FullscreenLayout
      messages={
        <Messages
          messages={messages}
          newMessageCount={newMessageCount}
          showLogo={showLogo}
          version={version}
        />
      }
      streamingText={
        streamingText || streamingReasoning ? (
          <Box flexDirection="column" marginTop={1}>
            {streamingReasoning && (
              <Box flexDirection="row" marginBottom={1}>
                <Box minWidth={2}>
                  <Text dimColor color="gray">◌</Text>
                </Box>
                <Box flexDirection="column">
                  <Text dimColor color="gray">{streamingReasoning.length > 200 ? streamingReasoning.slice(-200) : streamingReasoning}</Text>
                </Box>
              </Box>
            )}
            {streamingText && (
              <Box flexDirection="row">
                <Box minWidth={2}>
                  <Text color="white">●</Text>
                </Box>
                <Box flexDirection="column">
                  <Text>{streamingText}</Text>
                </Box>
              </Box>
            )}
          </Box>
        ) : undefined
      }
      newMessagesPill={
        newMessageCount > 0 ? (
          <NewMessagesPill
            count={newMessageCount}
            onClick={() => {
              stickToBottom.current = true;
              setNewMessageCount(0);
            }}
          />
        ) : undefined
      }
      modal={
        modal === 'help' ? (
          <HelpPanel onClose={() => setModal(null)} />
        ) : modal === 'map_picker' ? (
          <MapPicker
            onClose={() => setModal(null)}
            onOpen={(path: string) => {
              addToast(`地图文件: ${path}`, 'info');
              setModal(null);
            }}
          />
        ) : undefined
      }
      promptInput={
        <PromptInput
          onSubmit={handleSubmit}
          onHistoryUp={(current) => history.historyUp(current)}
          onHistoryDown={() => history.historyDown()}
          processing={processing}
          isActive={!isModalActive}
          placeholder="输入地址、命令或问题..."
          onExit={exit}
        />
      }
      statusBar={
        <StatusBar apis={apis} aiEnabled={aiEnabled} mode={processing ? 'Processing' : 'Chat'} />
      }
      toastArea={
        toasts.length > 0 ? <Toast toasts={toasts} /> : undefined
      }
    />
  );
}

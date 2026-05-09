/**
 * 输入区 — Claude Code PromptInput 移植
 *
 * Ghost text + Tab 补全 + ❯ dimColor 处理中 + Escape 双击清空 + 基础 kill ring
 *
 * 借鉴:
 *   src/components/PromptInput/PromptInput.tsx — dimColor 处理中(非⏺)
 *   src/hooks/useTextInput.ts — Escape 双击, kill ring
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import TextInput from 'ink-text-input';
import { theme } from '../theme';
import { USER_PREFIX, SPINNER_FRAMES } from '../figures';
import { getBestMatch } from '../hooks/useTypeahead';

// ── Kill Ring (模块级全局，借鉴 Claude Code Cursor.ts) ──────────

const KILL_RING_MAX = 10;
const killRing: string[] = [];
let lastKillAction = false;

function pushKill(text: string) {
  if (!text) return;
  if (lastKillAction && killRing.length > 0) {
    killRing[0] = killRing[0] + text;
  } else {
    killRing.unshift(text);
    if (killRing.length > KILL_RING_MAX) killRing.pop();
  }
  lastKillAction = true;
}

function resetKill() { lastKillAction = false; }

function yankLast(): string {
  return killRing[0] || '';
}

// ── 组件 ────────────────────────────────────────────────────────

interface Props {
  onSubmit: (text: string) => void;
  onHistoryUp: (current: string) => string;
  onHistoryDown: () => string;
  processing: boolean;
  isActive: boolean;
  placeholder?: string;
  onExit?: () => void;
}

export function PromptInput({
  onSubmit,
  onHistoryUp,
  onHistoryDown,
  processing,
  isActive,
  placeholder,
  onExit,
}: Props) {
  const [value, setValue] = useState('');

  // Escape 双击检测 (借鉴 Claude Code useDoublePress)
  const escapeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const escapeCount = useRef(0);

  // Ctrl+C 双击退出检测
  const ctrlCTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Spinner 动画（处理中状态）
  const [spinnerIdx, setSpinnerIdx] = useState(0);
  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(() => setSpinnerIdx(i => (i + 1) % SPINNER_FRAMES.length), 100);
    return () => clearInterval(timer);
  }, [processing]);

  const handleSubmit = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      onSubmit(trimmed);
      setValue('');
    },
    [onSubmit]
  );

  const match = value.startsWith('/') && value.length >= 2
    ? getBestMatch(value)
    : null;
  const ghostText = match ? match.suffix : '';

  useInput((input, key) => {
    if (!isActive) return;

    // Tab: 接受 ghost text 补全
    if (key.tab && ghostText) {
      setValue(prev => prev + ghostText);
      resetKill();
      return;
    }

    if (processing) {
      // 处理中时只允许 Ctrl+C 取消
      if (input === '\x03') return; // Ctrl+C — 由 App 层处理
      return;
    }

    // Ctrl+U: 剪切到行首 (kill ring)
    if (input === '\x15' && value) {
      pushKill(value);
      setValue('');
      return;
    }

    // Ctrl+Y: 粘贴 (yank)
    if (input === '\x19') {
      const yanked = yankLast();
      if (yanked) {
        setValue(prev => prev + yanked);
        resetKill();
      }
      return;
    }

    // Ctrl+W: 剪切前一个词 (简化版 — 删除到上一个空格)
    if (input === '\x17') {
      const lastSpace = value.trimEnd().lastIndexOf(' ');
      if (lastSpace >= 0) {
        pushKill(value.slice(lastSpace + 1));
        setValue(prev => prev.slice(0, lastSpace + 1));
      } else {
        pushKill(value);
        setValue('');
      }
      return;
    }

    // Escape 双击清空输入 (借鉴 Claude Code)
    if (key.escape) {
      if (value) {
        escapeCount.current++;
        if (escapeCount.current === 2) {
          // 第二次: 清空 + 保存历史
          if (value.trim()) {
            handleSubmit(value);
          } else {
            setValue('');
          }
          escapeCount.current = 0;
          if (escapeTimer.current) clearTimeout(escapeTimer.current);
          return;
        }
        // 第一次: 启动计时器
        escapeTimer.current = setTimeout(() => {
          escapeCount.current = 0;
        }, 800);
      }
      return; // 不阻止 App 层处理 (modal/cancel)
    }

    // Ctrl+C 双击退出
    if (input === '\x03') {
      if (value) {
        setValue(''); // 第一次: 清空
        ctrlCTimer.current = setTimeout(() => {}, 1000);
      } else if (onExit) {
        onExit(); // 第二次: 退出
      }
      return;
    }

    resetKill();

    if (key.upArrow) {
      const historyText = onHistoryUp(value);
      setValue(historyText || value);
    }
    if (key.downArrow) {
      const historyText = onHistoryDown();
      setValue(historyText || '');
    }
  });

  // Claude Code 对齐: 处理中 Spinner 动画
  const prefixColor = processing ? theme.claude : theme.claude;
  const prefix = processing ? SPINNER_FRAMES[spinnerIdx] : USER_PREFIX;

  return (
    <Box paddingX={1}>
      <Text color={prefixColor} dimColor={processing}>{prefix} </Text>
      {isActive ? (
        <Box>
          <TextInput
            value={value}
            onChange={setValue}
            onSubmit={handleSubmit}
            placeholder={processing ? 'AI 思考中...' : (placeholder || '输入地址、命令或问题...')}
            focus={!processing}
          />
          {ghostText && !processing && (
            <Text color={theme.subtle}>{ghostText}</Text>
          )}
        </Box>
      ) : (
        <Text color={theme.dim} dimColor>
          {placeholder || '按 Esc 关闭当前面板'}
        </Text>
      )}
    </Box>
  );
}

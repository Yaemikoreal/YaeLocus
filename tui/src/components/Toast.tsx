/**
 * Toast 通知 — info/success/warning 3秒消失，error 持久化
 *
 * 借鉴 Claude Code Feedback.tsx 的错误持久化模式
 */

import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import { theme } from '../theme';

export interface ToastData {
  id: string;
  message: string;
  level: 'info' | 'success' | 'warning' | 'error';
  persistent?: boolean;  // 新增：持久化选项（error 默认持久化）
}

interface Props {
  toasts: ToastData[];
}

const LEVEL_ICONS: Record<string, string> = {
  info: 'ℹ',
  success: '✓',
  warning: '⚠',
  error: '✗',
};

const LEVEL_COLORS: Record<string, string> = {
  info: theme.suggestion,
  success: theme.success,
  warning: theme.warning,
  error: theme.error,
};

export function Toast({ toasts }: Props) {
  if (toasts.length === 0) return null;

  return (
    <Box flexDirection="column">
      {toasts.slice(0, 3).map(t => (
        <Box key={t.id} paddingX={1}>
          <Text color={LEVEL_COLORS[t.level]}>
            {LEVEL_ICONS[t.level]} {t.message}
            {t.persistent && (
              <Text color={theme.subtle}> [按 Enter 关闭]</Text>
            )}
          </Text>
        </Box>
      ))}
    </Box>
  );
}

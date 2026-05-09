/**
 * 工具执行消息 — 运行中显示计时器，完成后隐藏，失败显示错误
 *
 * 借鉴 Claude Code ToolUseLoader.tsx: blink 动画
 */

import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import { theme } from '../theme';
import { TOOL_GEAR, BLACK_CIRCLE, CROSS_MARK, CHECK_MARK } from '../figures';
import { ToolResult } from './ToolResult';

interface Props {
  command: string;
  status: 'running' | 'done' | 'error';
  result?: string;
  exitCode?: number;
  elapsedTime?: number;  // 新增：执行耗时
}

export function ToolUseMessage({ command, status, result, exitCode, elapsedTime }: Props) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (status !== 'running') {
      setVisible(true);
      return;
    }
    const timer = setInterval(() => setVisible(v => !v), 600);
    return () => clearInterval(timer);
  }, [status]);

  // 成功后显示确认消息（而非 return null）
  if (status === 'done') {
    return (
      <Box paddingLeft={2}>
        <Text color={theme.success}>{CHECK_MARK} </Text>
        <Text color={theme.dim}>命令已完成</Text>
        {elapsedTime && <Text color={theme.subtle}> ({elapsedTime}s)</Text>}
      </Box>
    );
  }

  const dotColor = status === 'running'
    ? (visible ? theme.claude : undefined)
    : theme.error;

  const prefix = status === 'error' ? CROSS_MARK : TOOL_GEAR;

  return (
    <Text>
      <Text color={dotColor}>{BLACK_CIRCLE} </Text>
      <Text color={status === 'running' ? theme.claude : theme.error}>{prefix} </Text>
      <Text color={status === 'running' ? theme.text : theme.inactive}>{command}</Text>
      {result && (
        <ToolResult output={result} exitCode={exitCode} />
      )}
    </Text>
  );
}

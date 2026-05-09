/**
 * 命令结果渲染 — 格式化 CLI 输出为 TUI 友好的显示
 *
 * - 自动剥离 ANSI/Rich 控制字符
 * - 表格数据 → 紧凑对齐
 * - 纯文本 → dim 缩进
 * - 超过 20 行 → 截断
 */

import React from 'react';
import { Box, Text } from 'ink';
import { theme } from '../theme';

interface Props {
  output: string;
  exitCode?: number;
}

/** 剥离 ANSI 转义序列和 Rich 标记 */
function stripAnsi(text: string): string {
  return text
    .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')  // ANSI escape sequences
    .replace(/[─-╿]/g, '')           // box-drawing chars
    .replace(/\r/g, '')
    .trim();
}

/** 检测并格式化为紧凑表格 */
function formatTable(lines: string[]): string {
  // 检测 Rich 风格表格（含 │ ─ ┌ └ 等字符已剥离，只剩空格分隔）
  // 简单版本：每行用 2+ 个连续空格分隔的识别为表格
  const rows = lines
    .filter(l => l.trim())
    .map(l => l.trim().split(/\s{2,}/));

  if (rows.length < 2 || rows[0].length < 2) return lines.join('\n');

  // 计算列宽
  const colWidths: number[] = [];
  for (const row of rows) {
    for (let i = 0; i < row.length; i++) {
      colWidths[i] = Math.max(colWidths[i] || 0, row[i].length);
    }
  }

  // 对齐输出
  return rows.map(row =>
    row.map((cell, i) => cell.padEnd(colWidths[i] || 0)).join('  ')
  ).join('\n');
}

export function ToolResult({ output, exitCode }: Props) {
  const clean = stripAnsi(output);
  if (!clean && exitCode === 0) return null;

  const lines = clean.split('\n');
  const MAX_LINES = 20;
  const truncated = lines.length > MAX_LINES;

  const displayLines = truncated ? lines.slice(0, MAX_LINES) : lines;
  const formatted = formatTable(displayLines);

  const isError = exitCode !== undefined && exitCode !== 0;

  return (
    <Box flexDirection="column" paddingLeft={2}>
      <Text color={isError ? theme.error : theme.dim}>
        {formatted}
      </Text>
      {truncated && (
        <Text color={theme.subtle}>
          输出已截断 ({lines.length} 行)
        </Text>
      )}
    </Box>
  );
}

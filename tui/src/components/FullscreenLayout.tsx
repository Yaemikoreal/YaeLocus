/**
 * 全屏布局 — 消息区 + 模态 + 输入区（固定底部）
 *
 * 借鉴 Claude Code FullscreenLayout.tsx
 */

import React from 'react';
import { Box, Text } from 'ink';
import { theme } from '../theme';

interface Props {
  messages: React.ReactNode;
  streamingText?: React.ReactNode;
  newMessagesPill?: React.ReactNode;
  modal?: React.ReactNode;
  promptInput: React.ReactNode;
  statusBar: React.ReactNode;
  toastArea?: React.ReactNode;
}

export function FullscreenLayout({
  messages,
  streamingText,
  newMessagesPill,
  modal,
  promptInput,
  statusBar,
  toastArea,
}: Props) {
  return (
    <Box flexDirection="column" minHeight="100%">
      {/* 顶部: 消息区（可滚动） */}
      <Box flexGrow={1} flexDirection="column">
        {toastArea}
        {messages}
        {/* 流式文本 — 独立渲染在消息列表之上，借鉴 Claude Code */}
        {streamingText}
        {newMessagesPill}
      </Box>

      {/* 模态面板（在输入区上方，借鉴 Claude Code 的 modal slot） */}
      {modal}

      {/* 底部: 输入区（借鉴 flexShrink={0}） */}
      <Box flexDirection="column" flexShrink={0} width="100%">
        <Box height={1}>
          <Text color={theme.border}> </Text>
        </Box>
        {promptInput}
        {statusBar}
      </Box>
    </Box>
  );
}

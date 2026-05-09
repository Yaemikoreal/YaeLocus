/**
 * AI 助手消息渲染 — ● 前缀 (白色) + 流式脉冲
 *
 * 借鉴 Claude Code AssistantTextMessage.tsx
 */

import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import { theme } from '../theme';
import { BLACK_CIRCLE, STREAMING_PULSE } from '../figures';

interface Props {
  content: string;
  streaming?: boolean;
}

export function AssistantMessage({ content, streaming }: Props) {
  // 流式脉冲动画 — 300ms 间隔
  const [pulseIdx, setPulseIdx] = useState(0);

  useEffect(() => {
    if (!streaming) return;
    const timer = setInterval(() => setPulseIdx(i => (i + 1) % STREAMING_PULSE.length), 300);
    return () => clearInterval(timer);
  }, [streaming]);

  const prefix = streaming
    ? STREAMING_PULSE[pulseIdx]
    : BLACK_CIRCLE;

  const prefixColor = streaming ? theme.claudeShimmer : 'white';

  return (
    <Box>
      <Text>
        <Text color={prefixColor}>{prefix} </Text>
        <Text>{content}</Text>
        {streaming && <Text color={theme.claudeShimmer}>▌</Text>}
      </Text>
    </Box>
  );
}

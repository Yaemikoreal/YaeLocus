/**
 * 状态栏 — Claude Code PromptInputFooter 移植
 *
 * 使用 Byline 组件 + middot 分隔符
 * 借鉴: src/components/PromptInput/PromptInputFooterLeftSide.tsx
 */

import React from 'react';
import { Box, Text } from 'ink';
import { theme } from '../theme';
import { Byline } from './Byline';
import { CHECK_MARK } from '../figures';

interface Props {
  apis: string[];
  aiEnabled: boolean;
  mode: string;
}

export function StatusBar({ apis, aiEnabled, mode }: Props) {
  const isProcessing = mode === 'Processing';

  return (
    <Box paddingX={1} height={1} overflow="hidden">
      <Byline>
        <Text color={isProcessing ? theme.claudeShimmer : theme.text}>
          {isProcessing ? '处理中' : 'Chat'}
        </Text>
        {apis.map(api => (
          <Text key={api} color={theme.success}>
            {CHECK_MARK}{api}
          </Text>
        ))}
        {aiEnabled && (
          <Text color={theme.claude}>AI</Text>
        )}
        <Text color={theme.subtle}>Ctrl+C 取消</Text>
        <Text color={theme.subtle}>Tab 补全</Text>
        <Text color={theme.subtle}>/help</Text>
      </Byline>
    </Box>
  );
}

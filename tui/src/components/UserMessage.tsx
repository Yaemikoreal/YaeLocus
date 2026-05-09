/**
 * 用户消息渲染 — ❯ 前缀 (Claude 橙) + 背景色
 *
 * 借鉴 Claude Code UserPromptMessage.tsx
 */

import React from 'react';
import { Box, Text } from 'ink';
import { theme } from '../theme';
import { USER_PREFIX } from '../figures';

interface Props {
  content: string;
}

export function UserMessage({ content }: Props) {
  return (
    <Box paddingRight={1}>
      <Text backgroundColor={theme.userMessageBackground}>
        <Text color={theme.claude}>{USER_PREFIX} </Text>
        <Text>{content}</Text>
      </Text>
    </Box>
  );
}

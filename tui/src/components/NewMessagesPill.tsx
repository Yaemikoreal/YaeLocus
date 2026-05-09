/**
 * 浮动 "N 条新消息" 药丸 — 当用户滚动离开底部时显示
 *
 * 借鉴 Claude Code NewMessagesPill
 */

import React from 'react';
import { Box, Text } from 'ink';
import { theme } from '../theme';
import { DOWN_ARROW } from '../figures';

interface Props {
  count: number;
  onClick: () => void;
}

export function NewMessagesPill({ count, onClick }: Props) {
  if (count <= 0) return null;

  return (
    <Box justifyContent="flex-end" paddingRight={2} paddingBottom={1}>
      <Text backgroundColor={theme.claude} color={theme.inverseText}>
        {' '}{DOWN_ARROW} {count} 条新消息{' '}
      </Text>
    </Box>
  );
}

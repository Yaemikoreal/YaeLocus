/**
 * 消息列表 — Logo + 新消息分隔线 + 消息行
 *
 * 借鉴 Claude Code Messages.tsx: 间距、分隔线样式
 */

import React from 'react';
import { Box, Text } from 'ink';
import { Message, MessageData } from './Message';
import { theme } from '../theme';
import { HEAVY_HORIZONTAL } from '../figures';

interface Props {
  messages: MessageData[];
  newMessageCount: number;
  showLogo: boolean;
  version: string;
}

export function Messages({ messages, newMessageCount, showLogo, version }: Props) {
  return (
    <Box flexDirection="column" paddingX={1}>
      {showLogo && (
        <Box flexDirection="column" marginY={1}>
          <Text>
            <Text color={theme.claude} bold>  YaeLocus</Text>
            <Text color={theme.dim}> v{version}</Text>
          </Text>
          <Text color={theme.subtle}>  geocode · route · ai · optimize</Text>
          <Box marginY={1}>
            <Text color={theme.border}>  {'─'.repeat(40)}</Text>
          </Box>
        </Box>
      )}

      {messages.map((msg, i) => {
        const isNewMessageDivider =
          newMessageCount > 0 &&
          i === messages.length - newMessageCount;

        // 消息间距: 借鉴 Claude Code marginTop 模式
        const prevRole = i > 0 ? messages[i - 1].role : null;
        const addMargin = prevRole && prevRole !== msg.role;

        return (
          <Box key={msg.id} flexDirection="column">
            {isNewMessageDivider && (
              <Box marginY={1}>
                <Text color={theme.subtle}>
                  {HEAVY_HORIZONTAL.repeat(3)} {newMessageCount} 条新消息 {HEAVY_HORIZONTAL.repeat(3)}
                </Text>
              </Box>
            )}
            <Box marginTop={addMargin ? 1 : 0}>
              <Message message={msg} />
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}

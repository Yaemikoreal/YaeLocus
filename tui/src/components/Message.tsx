/**
 * 消息调度器 — 按类型路由到对应渲染组件
 *
 * 借鉴 Claude Code Message.tsx 的调度模式
 */

import React from 'react';
import { Text } from 'ink';
import { UserMessage } from './UserMessage';
import { AssistantMessage } from './AssistantMessage';
import { ToolUseMessage } from './ToolUseMessage';
import { theme } from '../theme';

export interface MessageData {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool' | 'error';
  content: string;
  streaming?: boolean;
  toolCommand?: string;
  toolStatus?: 'running' | 'done' | 'error';
  toolResult?: string;
}

interface Props {
  message: MessageData;
}

export function Message({ message }: Props) {
  switch (message.role) {
    case 'user':
      return <UserMessage content={message.content} />;

    case 'assistant':
      return <AssistantMessage content={message.content} streaming={message.streaming} />;

    case 'tool':
      return (
        <ToolUseMessage
          command={message.toolCommand || message.content}
          status={message.toolStatus || 'running'}
          result={message.toolResult}
        />
      );

    case 'error':
      return (
        <Text color={theme.error}>{message.content}</Text>
      );

    case 'system':
    default:
      return (
        <Text color={theme.dim}>{message.content}</Text>
      );
  }
}

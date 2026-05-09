/**
 * Byline — 用 · (middot) 连接子元素的排版组件
 *
 * 借鉴 Claude Code src/components/design-system/Byline.tsx
 */

import React, { Children, isValidElement } from 'react';
import { Text } from 'ink';
import { theme } from '../theme';
import { BULLET_OPERATOR } from '../figures';

interface Props {
  children: React.ReactNode;
}

export function Byline({ children }: Props) {
  const items = Children.toArray(children).filter(
    c => isValidElement(c) || (typeof c === 'string' && c.length > 0)
  );

  return (
    <Text>
      {items.map((item, i) => (
        <React.Fragment key={i}>
          {i > 0 && <Text color={theme.subtle}> {BULLET_OPERATOR} </Text>}
          {item}
        </React.Fragment>
      ))}
    </Text>
  );
}

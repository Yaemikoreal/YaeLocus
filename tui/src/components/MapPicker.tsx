/**
 * 地图文件选择器模态 — 方向键选择，Enter 在浏览器中打开
 *
 * 借鉴 Claude Code Dialog.tsx + Pane.tsx
 */

import React, { useState, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import { theme } from '../theme';
import { MODAL_SEPARATOR, USER_PREFIX, CHECK_MARK } from '../figures';
import { useAPI, MapEntry } from '../hooks/useAPI';

interface Props {
  onClose: () => void;
  onOpen: (path: string) => void;
}

export function MapPicker({ onClose, onOpen }: Props) {
  const [maps, setMaps] = useState<MapEntry[]>([]);
  const [selected, setSelected] = useState(0);
  const [loading, setLoading] = useState(true);
  const api = useAPI();

  useEffect(() => {
    api.listMaps().then(res => {
      setMaps(res.maps);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  // BUG #1 修复: 键盘处理
  useInput((_input, key) => {
    if (key.upArrow) {
      setSelected(s => Math.max(0, s - 1));
      return;
    }
    if (key.downArrow) {
      setSelected(s => Math.min((maps.length || 1) - 1, s + 1));
      return;
    }
    if (key.return) {
      const file = maps[selected];
      if (file) {
        onOpen(file.path);
        api.openFile(file.path).catch(() => {});
      }
      return;
    }
    if (key.escape) {
      onClose();
      return;
    }
  }, { isActive: true });

  const cols = process.stdout.columns || 60;

  return (
    <Box flexDirection="column" paddingTop={1}>
      {/* Claude Code Pane 风格: 顶部分隔线 */}
      <Box flexShrink={0}>
        <Text color={theme.permission}>{MODAL_SEPARATOR.repeat(cols)}</Text>
      </Box>

      <Box flexDirection="column" paddingX={2}>
        <Box marginTop={1}>
          <Text bold color={theme.claude}>  地图文件浏览器</Text>
        </Box>

        {/* Byline 风格的键盘提示 */}
        <Box marginBottom={1}>
          <Text color={theme.dim}>
            {'  '}{USER_PREFIX}{' '}
          </Text>
          <Text color={theme.subtle}>选择</Text>
          <Text color={theme.dim}> · </Text>
          <Text color={theme.suggestion}>Enter</Text>
          <Text color={theme.dim}> 打开 · </Text>
          <Text color={theme.suggestion}>Esc</Text>
          <Text color={theme.dim}> 返回</Text>
        </Box>

        <Box flexDirection="column">
          {loading ? (
            <Text color={theme.dim}>  ⠋ 加载中...</Text>
          ) : maps.length === 0 ? (
            <Text color={theme.dim}>  (暂无地图文件 — 请先运行 geocode batch 或 map create)</Text>
          ) : (
            maps.map((m, i) => {
              const isSelected = i === selected;
              return (
                <Box key={m.name}>
                  <Text color={isSelected ? theme.claude : theme.dim}>
                    {isSelected ? USER_PREFIX : ' '}{' '}
                  </Text>
                  <Text
                    color={isSelected ? theme.text : theme.inactive}
                    backgroundColor={isSelected ? theme.selectionBg : undefined}
                  >
                    {m.name} ({m.size_kb.toFixed(0)} KB)
                  </Text>
                </Box>
              );
            })
          )}
        </Box>
      </Box>
    </Box>
  );
}

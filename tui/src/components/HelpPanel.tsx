/**
 * 帮助面板 — 显示所有可用命令
 */

import React from 'react';
import { Box, Text } from 'ink';
import { theme } from '../theme';
import { MODAL_SEPARATOR } from '../figures';

interface Props {
  onClose: () => void;
}

const COMMANDS = [
  ['geocode single <地址>', '单地址转经纬度'],
  ['geocode batch -i <文件>', '批量编码→CSV+地图'],
  ['geocode reverse <lat> <lon>', '经纬度转地址'],
  ['geocode convert <lat> <lon>', '坐标系转换'],
  ['map list', '列出可处理文件'],
  ['map create -i <csv>', '从CSV生成地图'],
  ['ai chat <消息>', 'AI 对话'],
  ['ai analyze -i <csv>', 'AI 数据分析'],
  ['ai route -i <csv>', 'AI 路线规划'],
  ['config setup', '配置 API 密钥'],
  ['config check', '环境诊断'],
  ['config cache stats', '缓存统计'],
];

const SLASH_COMMANDS = [
  ['/help', '显示帮助'],
  ['/clear', '清屏'],
  ['/quit', '退出'],
  ['/status', '显示状态'],
  ['/export', '导出会话'],
  ['/map', '地图文件浏览器'],
  ['/geocode <地址>', '快速编码'],
];

export function HelpPanel({ onClose }: Props) {
  return (
    <Box flexDirection="column" paddingX={2} paddingBottom={1}>
      <Box flexShrink={0}>
        <Text color={theme.permission}>{MODAL_SEPARATOR.repeat(process.stdout.columns || 60)}</Text>
      </Box>
      <Box flexDirection="column" paddingX={1}>
        <Text color={theme.claude} bold>  YaeLocus 帮助</Text>
        <Text color={theme.dim}>  命令    │  说明</Text>

        {COMMANDS.map(([cmd, desc]) => (
          <Box key={cmd}>
            <Text color={theme.suggestion}>  {cmd.padEnd(32)}</Text>
            <Text color={theme.dim}>{desc}</Text>
          </Box>
        ))}

        <Box marginTop={1}>
          <Text color={theme.dim}>  快捷命令:</Text>
        </Box>
        {SLASH_COMMANDS.map(([cmd, desc]) => (
          <Box key={cmd}>
            <Text color={theme.suggestion}>  {cmd.padEnd(20)}</Text>
            <Text color={theme.dim}>{desc}</Text>
          </Box>
        ))}

        <Box marginTop={1}>
          <Text color={theme.dim}>  Esc 关闭  |  直接输入自然语言也可以让 AI 帮你</Text>
        </Box>
      </Box>
    </Box>
  );
}

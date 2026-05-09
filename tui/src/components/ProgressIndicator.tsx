/**
 * 多步骤进度指示器 — 借鉴 Claude Code TeleportProgress.tsx 步骤模式
 *
 * 显示: ○ 待处理, spinner 进行中, ✓ 完成
 */

import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import { theme } from '../theme';
import { CHECK_MARK, BLACK_CIRCLE, SPINNER_FRAMES } from '../figures';

export interface ProgressStep {
  key: string;
  label: string;
  status: 'pending' | 'running' | 'done';
  progress?: {
    current: number;
    total: number;
    success?: number;
  };
}

interface Props {
  steps: ProgressStep[];
  elapsedTime?: number;
}

export function ProgressIndicator({ steps, elapsedTime }: Props) {
  const [spinnerIdx, setSpinnerIdx] = useState(0);

  // Spinner 动画（有进行中步骤时启动）
  useEffect(() => {
    const hasRunning = steps.some(s => s.status === 'running');
    if (!hasRunning) return;
    const timer = setInterval(
      () => setSpinnerIdx(i => (i + 1) % SPINNER_FRAMES.length),
      100
    );
    return () => clearInterval(timer);
  }, [steps]);

  // 计算总进度百分比
  const runningStep = steps.find(s => s.status === 'running');
  const overallPercent = runningStep?.progress
    ? Math.round((runningStep.progress.current / runningStep.progress.total) * 100)
    : undefined;

  return (
    <Box flexDirection="column" paddingLeft={2}>
      {steps.map((step) => {
        // 状态图标选择
        const icon = step.status === 'done'
          ? CHECK_MARK
          : step.status === 'running'
            ? SPINNER_FRAMES[spinnerIdx]
            : BLACK_CIRCLE;

        // 颜色选择
        const color = step.status === 'done'
          ? theme.success
          : step.status === 'running'
            ? theme.claude
            : theme.dim;

        // 进度文本
        const progressText = step.progress
          ? ` (${step.progress.current}/${step.progress.total}${step.progress.success !== undefined ? `, 成功: ${step.progress.success}` : ''})`
          : '';

        return (
          <Box key={step.key}>
            <Text color={color}>{icon} </Text>
            <Text color={step.status === 'pending' ? theme.dim : theme.text}>
              {step.label}{progressText}
            </Text>
          </Box>
        );
      })}

      {/* 总进度百分比 */}
      {overallPercent !== undefined && (
        <Box marginTop={1}>
          <Text color={theme.subtle}>
            总进度: {overallPercent}% ({runningStep?.progress?.current}/{runningStep?.progress?.total})
          </Text>
        </Box>
      )}

      {/* 已用时 */}
      {elapsedTime && (
        <Box>
          <Text color={theme.subtle}>已用时: {elapsedTime}s</Text>
        </Box>
      )}
    </Box>
  );
}

/**
 * 创建初始步骤配置
 */
export function createInitialSteps(): ProgressStep[] {
  return [
    { key: 'reading', label: '读取文件', status: 'pending' },
    { key: 'processing', label: '处理地址', status: 'pending' },
    { key: 'saving', label: '保存结果', status: 'pending' },
  ];
}

/**
 * 更新步骤状态
 */
export function updateStepStatus(
  steps: ProgressStep[],
  key: string,
  status: ProgressStep['status'],
  progress?: ProgressStep['progress']
): ProgressStep[] {
  return steps.map(s =>
    s.key === key ? { ...s, status, ...(progress && { progress }) } : s
  );
}
/**
 * YaeLocus TUI 入口
 *
 * React Ink 渲染入口 — 与 Claude Code 完全相同的框架
 */

import React from 'react';
import { render } from 'ink';
import { App } from './App';

const { unmount, waitUntilExit } = render(<App />);

// 在退出时清理
process.on('SIGINT', () => {
  unmount();
  process.exit(0);
});

process.on('SIGTERM', () => {
  unmount();
  process.exit(0);
});

waitUntilExit().then(() => {
  process.exit(0);
});

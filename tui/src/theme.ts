/**
 * YaeLocus TUI 配色 — 完全对齐 Claude Code dark theme
 *
 * 从 claude-code-source/src/utils/theme.ts 移植
 */

export interface Theme {
  claude: string;
  claudeShimmer: string;
  text: string;
  inverseText: string;
  inactive: string;
  subtle: string;
  suggestion: string;
  error: string;
  success: string;
  warning: string;
  permission: string;
  background: string;
  userMessageBackground: string;
  userMessageBackgroundHover: string;
  bashMessageBackgroundColor: string;
  messageActionsBackground: string;
  selectionBg: string;
  fastMode: string;
  diffAdded: string;
  diffRemoved: string;
  planMode: string;
  autoAccept: string;
  codeBackground: string;
  border: string;
  dim: string;
}

export const darkTheme: Theme = {
  /** Claude 品牌橙 — 用于标题、边框、用户前缀、高亮 */
  claude: 'rgb(215,119,87)',
  /** 品牌橙的微光变体 */
  claudeShimmer: 'rgb(235,159,127)',
  /** 主要文本颜色 */
  text: 'rgb(255,255,255)',
  /** 反色文本（在亮色背景上） */
  inverseText: 'rgb(0,0,0)',
  /** 暗淡/非活动文本 */
  inactive: 'rgb(153,153,153)',
  /** 微妙文本（分隔线、占位符等） */
  subtle: 'rgb(80,80,80)',
  /** 建议/链接颜色 */
  suggestion: 'rgb(177,185,249)',
  /** 错误 */
  error: 'rgb(255,107,128)',
  /** 成功 */
  success: 'rgb(78,186,101)',
  /** 警告 */
  warning: 'rgb(255,193,7)',
  /** 权限/确认相关 */
  permission: 'rgb(177,185,249)',
  /** 背景强调 */
  background: 'rgb(30,30,30)',
  /** 用户消息气泡背景 */
  userMessageBackground: 'rgb(55,55,55)',
  /** 用户消息气泡悬停 */
  userMessageBackgroundHover: 'rgb(70,70,70)',
  /** Bash/代码消息背景 */
  bashMessageBackgroundColor: 'rgb(65,60,65)',
  /** 消息操作选择背景 */
  messageActionsBackground: 'rgb(44,50,62)',
  /** 文本选择高亮 */
  selectionBg: 'rgb(38,79,120)',
  /** 快速模式指示器 */
  fastMode: 'rgb(255,120,20)',
  /** Diff 添加 */
  diffAdded: 'rgb(34,92,43)',
  /** Diff 删除 */
  diffRemoved: 'rgb(122,41,54)',
  /** 计划模式 */
  planMode: 'rgb(72,150,140)',
  /** 自动接受 */
  autoAccept: 'rgb(175,135,255)',
  /** 代码块背景 */
  codeBackground: 'rgb(42,42,42)',
  /** 边框 */
  border: 'rgb(80,80,80)',
  /** 最淡的文字 */
  dim: 'rgb(100,100,100)',
};

/** alias for backward compatibility */
export const theme = darkTheme;

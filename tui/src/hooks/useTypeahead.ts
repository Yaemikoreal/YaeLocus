/**
 * 命令自动补全 — Fuse.js 模糊匹配 + ghost text 生成
 *
 * 借鉴 Claude Code src/utils/suggestions/commandSuggestions.ts:
 *   Fuse.js threshold: 0.3, 权重: name×3, alias×2, desc×0.5
 */

import Fuse from 'fuse.js';

// ── 命令定义 ──────────────────────────────────────────────────────

interface CommandDef {
  name: string;
  aliases?: string[];
  description: string;
}

const COMMANDS: CommandDef[] = [
  { name: '/help', aliases: ['/h'], description: '显示帮助' },
  { name: '/clear', description: '清屏' },
  { name: '/quit', aliases: ['/q', '/exit'], description: '退出' },
  { name: '/status', description: '显示状态' },
  { name: '/export', description: '导出会话历史' },
  { name: '/geocode', description: '快速编码单个地址' },
  { name: '/config', description: '配置管理 (setup/check/test-api)' },
  { name: '/map', description: '打开地图文件选择器' },
  { name: '/cache', description: '查看缓存统计' },
  { name: '/sessions', description: '列出历史会话' },
  { name: '/doctor', description: '环境诊断' },
  { name: '/compact', description: '压缩上下文' },
  { name: '/copy', description: '复制最后 AI 回复到剪贴板' },
  { name: '/model', description: '显示 AI 模型配置' },
];

// ── Fuse.js 配置 ──────────────────────────────────────────────────

const fuse = new Fuse(COMMANDS, {
  includeScore: true,
  threshold: 0.3,
  location: 0,
  distance: 100,
  keys: [
    { name: 'name', weight: 3 },
    { name: 'aliases', weight: 2 },
    { name: 'description', weight: 0.5 },
  ],
});

// ── 补全 API ──────────────────────────────────────────────────────

export interface TypeaheadResult {
  /** 完整匹配的命令名 */
  command: string;
  /** ghost text（用户输入后的部分） */
  suffix: string;
  /** 命令描述 */
  description: string;
}

/**
 * 获取最佳补全匹配
 * @param input 用户当前输入（以 / 开头）
 * @returns 补全结果，无匹配时返回 null
 */
export function getBestMatch(input: string): TypeaheadResult | null {
  if (!input.startsWith('/') || input.length < 2) return null;

  // 先检查精确前缀匹配（优先级高于 Fuse 模糊匹配）
  const exact = COMMANDS.find(c => c.name.startsWith(input));
  if (exact) {
    return {
      command: exact.name,
      suffix: exact.name.slice(input.length),
      description: exact.description,
    };
  }

  // 检查别名精确前缀匹配
  const aliasMatch = COMMANDS.find(c =>
    c.aliases?.some(a => a.startsWith(input))
  );
  if (aliasMatch) {
    const alias = aliasMatch.aliases!.find(a => a.startsWith(input))!;
    return {
      command: alias,
      suffix: alias.slice(input.length),
      description: aliasMatch.description,
    };
  }

  // Fuse.js 模糊匹配
  const results = fuse.search(input);
  if (results.length === 0) return null;

  const best = results[0].item;
  return {
    command: best.name,
    suffix: best.name.slice(input.length),
    description: best.description,
  };
}

/**
 * 获取所有匹配（用于下拉列表）
 */
export function getSuggestions(input: string): TypeaheadResult[] {
  if (!input.startsWith('/') || input.length < 2) return [];

  const results = fuse.search(input);
  return results.slice(0, 8).map(r => ({
    command: r.item.name,
    suffix: r.item.name.slice(input.length),
    description: r.item.description,
  }));
}

/**
 * 获取所有命令（用于 /help 展示）
 */
export function getAllCommands(): CommandDef[] {
  return COMMANDS;
}

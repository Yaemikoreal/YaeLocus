/**
 * 错误码映射 — 将 API 技术错误转为用户友好消息
 *
 * 借鉴 Claude Code UserToolErrorMessage.tsx 的错误处理模式
 */

export interface ErrorMapping {
  code: string;
  message: string;
  suggestion?: string;
  level: 'error' | 'warning';
}

const ERROR_MAP: Record<number, ErrorMapping> = {
  400: {
    code: 'INVALID_REQUEST',
    message: '请求格式错误',
    suggestion: '请检查输入参数是否正确',
    level: 'error'
  },
  401: {
    code: 'UNAUTHORIZED',
    message: 'API 密钥无效或未配置',
    suggestion: '请运行 yaelocus config setup 配置密钥',
    level: 'error'
  },
  403: {
    code: 'FORBIDDEN',
    message: '权限不足',
    suggestion: '请检查 API 密钥权限设置',
    level: 'error'
  },
  404: {
    code: 'NOT_FOUND',
    message: '资源不存在',
    suggestion: '请检查文件路径或地址是否正确',
    level: 'warning'
  },
  429: {
    code: 'RATE_LIMIT',
    message: '请求频率超限',
    suggestion: '请稍后再试或减少批量处理数量',
    level: 'warning'
  },
  500: {
    code: 'SERVER_ERROR',
    message: '服务器内部错误',
    suggestion: '请稍后再试，如持续失败请检查日志',
    level: 'error'
  },
  503: {
    code: 'SERVICE_UNAVAILABLE',
    message: 'AI 服务未启用',
    suggestion: '请配置 AI 密钥或使用基础地理编码功能',
    level: 'warning'
  },
};

// 特定错误内容匹配
const CONTENT_PATTERNS: Array<{
  pattern: RegExp;
  mapping: ErrorMapping;
}> = [
  {
    pattern: /column|列.*不存在/i,
    mapping: {
      code: 'COLUMN_NOT_FOUND',
      message: '地址列不存在',
      suggestion: '请使用 -c 参数指定正确的列名',
      level: 'error'
    }
  },
  {
    pattern: /file.*not.*found|文件不存在/i,
    mapping: {
      code: 'FILE_NOT_FOUND',
      message: '输入文件不存在',
      suggestion: '请检查文件路径是否正确',
      level: 'error'
    }
  },
  {
    pattern: /database.*locked|数据库.*锁定/i,
    mapping: {
      code: 'DATABASE_LOCKED',
      message: '数据库锁定，正在自动恢复...',
      suggestion: '请稍候，系统将自动处理',
      level: 'warning'
    }
  },
  {
    pattern: /no.*api.*key|未配置.*密钥/i,
    mapping: {
      code: 'NO_API_KEY',
      message: '未配置 API 密钥',
      suggestion: '请运行 yaelocus config setup 配置密钥',
      level: 'error'
    }
  },
];

/**
 * 将 API 错误状态码映射为用户友好消息
 */
export function mapAPIError(status: number, body?: string): ErrorMapping {
  // 先检查内容匹配
  if (body) {
    for (const { pattern, mapping } of CONTENT_PATTERNS) {
      if (pattern.test(body)) {
        return mapping;
      }
    }
  }

  // 使用状态码映射
  return ERROR_MAP[status] || {
    code: 'UNKNOWN',
    message: `未知错误 (${status})`,
    suggestion: '请查看日志文件获取详细信息',
    level: 'error'
  };
}

/**
 * 格式化错误消息供用户显示
 */
export function formatErrorForUser(error: Error | string): string {
  // 剥离 ANSI 代码
  const clean = String(error)
    .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')
    .replace(/\r/g, '')
    .trim();

  // 截断长错误
  if (clean.length > 200) {
    return clean.slice(0, 200) + '... [使用 --verbose 查看完整错误]';
  }

  return clean;
}

/**
 * 创建用户友好的错误消息字符串
 */
export function createUserErrorMessage(status: number, body?: string): string {
  const mapped = mapAPIError(status, body);
  let msg = mapped.message;
  if (mapped.suggestion) {
    msg += `\n建议: ${mapped.suggestion}`;
  }
  return msg;
}
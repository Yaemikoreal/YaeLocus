import { useState, useRef, useCallback, useEffect } from 'react'
import { agentStream } from '../../lib/api'
import type { AgentStreamCallbacks } from '../../lib/api'
import { useChatStore } from '../../lib/chatStore'
import type { ChatMessage } from '../../lib/types'
import { Send, Square, Plus, Download, Minimize2 } from 'lucide-react'
import MessageContent from './MessageContent'

const EMPTY_MESSAGES: ChatMessage[] = []

const SLASH_COMMANDS: Record<string, string> = {
  '/new': 'clear',
  '/clear': 'clear',
  '/compact': 'compact',
  '/export': 'export',
  '/model': 'model',
  '/help': 'help',
}

export default function ChatPanel() {
  const currentSessionId = useChatStore((s) => s.currentSessionId)
  const messages = useChatStore((s) => s.messages[s.currentSessionId] || EMPTY_MESSAGES)
  const addMessage = useChatStore((s) => s.addMessage)
  const updateMessage = useChatStore((s) => s.updateMessage)
  const clearCurrentSession = useChatStore((s) => s.clearCurrentSession)
  const compactCurrentSession = useChatStore((s) => s.compactCurrentSession)
  const exportCurrentSession = useChatStore((s) => s.exportCurrentSession)
  const newSession = useChatStore((s) => s.newSession)

  useEffect(() => {
    if (!currentSessionId) {
      newSession()
    }
  }, [currentSessionId, newSession])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState('')
  const [agentRound, setAgentRound] = useState(0)
  const [maxRounds, setMaxRounds] = useState(4)
  const streamContent = useRef('')
  const streamReasoning = useRef('')
  const lastRenderRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleCancel = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
    setAgentRound(0)
  }, [])

  const handleSlashCommand = useCallback((text: string): boolean => {
    const cmd = text.trim().toLowerCase()
    const action = SLASH_COMMANDS[cmd]
    if (!action) return false

    switch (action) {
      case 'clear':
        clearCurrentSession()
        return true
      case 'compact':
        compactCurrentSession()
        addMessage({ role: 'system', content: '上下文已压缩至最近 10 条消息' })
        return true
      case 'export': {
        const content = exportCurrentSession()
        if (!content) return true
        const blob = new Blob([content], { type: 'text/markdown' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `chat-${new Date().toISOString().slice(0, 10)}.md`
        a.click()
        URL.revokeObjectURL(url)
        return true
      }
      case 'help':
        addMessage({ role: 'system', content: '可用命令:\n/new — 新建对话\n/clear — 清空对话\n/compact — 压缩上下文\n/export — 导出对话\n/model — 显示当前模型\n/help — 显示帮助' })
        return true
      case 'model':
        fetch('/api/config').then(r => r.json()).then((cfg) => {
          const provider = cfg.ai_provider || 'unknown'
          const model = cfg.ai_model || 'unknown'
          addMessage({ role: 'system', content: `AI 模型: ${provider}/${model}` })
        }).catch(() => {
          addMessage({ role: 'system', content: '无法获取模型信息' })
        })
        return true
    }
    return false
  }, [clearCurrentSession, compactCurrentSession, addMessage, exportCurrentSession])

  const handleSend = useCallback(() => {
    const trimmed = input.trim()
    if (!trimmed || streaming) return

    if (trimmed.startsWith('/')) {
      if (handleSlashCommand(trimmed)) {
        setInput('')
        return
      }
    }

    addMessage({ role: 'user', content: trimmed })
    const assistantId = addMessage({ role: 'assistant', content: '', reasoning: '' })
    setInput('')
    setError('')
    setStreaming(true)
    setAgentRound(0)
    streamContent.current = ''
    streamReasoning.current = ''

    const controller = new AbortController()
    abortRef.current = controller

    const context: { role: string; content: string }[] = []
    const allMsgs = useChatStore.getState().messages[currentSessionId] || []
    for (const msg of allMsgs.slice(-30)) {
      if (msg.role === 'user' && msg.content) {
        context.push({ role: 'user', content: msg.content })
      } else if (msg.role === 'assistant' && msg.content) {
        context.push({ role: 'assistant', content: msg.content.slice(0, 800) })
      }
    }
    context.pop()

    const callbacks: AgentStreamCallbacks = {
      onContent: (token: string) => {
        streamContent.current += token
        const now = Date.now()
        if (now - lastRenderRef.current >= 50) {
          lastRenderRef.current = now
          updateMessage(assistantId, {
            content: streamContent.current,
            reasoning: streamReasoning.current,
          })
          scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
        }
      },
      onReasoning: (token: string) => {
        streamReasoning.current += token
        const now = Date.now()
        if (now - lastRenderRef.current >= 100) {
          lastRenderRef.current = now
          updateMessage(assistantId, {
            reasoning: streamReasoning.current,
            content: streamContent.current,
          })
        }
      },
      onToolUse: () => {
        updateMessage(assistantId, {
          content: streamContent.current,
          reasoning: streamReasoning.current,
        })
      },
      onToolUseDelta: () => {},
      onToolResult: (result) => {
        const toolMsg = `⏺ ${result.command}${result.success ? '' : ' (失败)'}`
        // 移除前端二次截断，依赖后端截断（阈值 10000）
        streamContent.current += `\n${toolMsg}\n\`\`\`\n${result.result}\n\`\`\`\n`
        updateMessage(assistantId, {
          content: streamContent.current,
          reasoning: streamReasoning.current,
        })
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
      },
      onToolError: (err) => {
        const errorMsg = `⏺ ${err.command} — ${err.error.message}${err.recoverable ? ' (自动恢复中...)' : ''}`
        streamContent.current += `\n${errorMsg}\n`
        updateMessage(assistantId, {
          content: streamContent.current,
          reasoning: streamReasoning.current,
        })
      },
      onToolRecovery: (info) => {
        const msg = info.fix_command
          ? `⟳ 自动修复: ${info.fix_command}`
          : `⟳ 等待 ${info.wait_seconds}s 后重试...`
        streamContent.current += `\n${msg}\n`
        updateMessage(assistantId, {
          content: streamContent.current,
          reasoning: streamReasoning.current,
        })
      },
      onRoundStart: (info) => {
        setAgentRound(info.round)
        setMaxRounds(info.max_rounds)
      },
      onDone: () => {
        updateMessage(assistantId, {
          content: streamContent.current,
          reasoning: streamReasoning.current,
        })
        setStreaming(false)
        setAgentRound(0)
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
      },
      onError: (err) => {
        setError(`${err.message}`)
        updateMessage(assistantId, {
          content: streamContent.current || '(AI 响应异常)',
          reasoning: streamReasoning.current,
        })
        setStreaming(false)
        setAgentRound(0)
      },
    }

    agentStream(trimmed, callbacks, {
      context,
      sessionId: currentSessionId || undefined,
      signal: controller.signal,
    })
  }, [input, streaming, addMessage, updateMessage, handleSlashCommand, currentSessionId])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleTextareaInput = (e: React.FormEvent<HTMLTextAreaElement>) => {
    const el = e.currentTarget
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  return (
    <div className="chat-container">
      <div className="chat-toolbar">
        <button className="chat-toolbar-btn" onClick={() => clearCurrentSession()} title="新建对话">
          <Plus size={14} />
        </button>
        <button className="chat-toolbar-btn" onClick={() => compactCurrentSession()} title="压缩上下文">
          <Minimize2 size={14} />
        </button>
        <button className="chat-toolbar-btn"
          onClick={() => {
            const content = exportCurrentSession()
            if (content) {
              const blob = new Blob([content], { type: 'text/markdown' })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = `chat-${new Date().toISOString().slice(0, 10)}.md`
              a.click()
              URL.revokeObjectURL(url)
            }
          }}
          title="导出对话"
        >
          <Download size={14} />
        </button>
      </div>

      <div ref={scrollRef} className="chat-messages">
        {messages.length === 0 && !streaming && (
          <div className="chat-welcome">
            <div className="chat-welcome-icon">
              <i className="fa-solid fa-wand-magic-sparkles" />
            </div>
            <h3>YaeLocus AI 助手</h3>
            <p>基于地理数据的智能分析，支持数据洞察、路线规划和地址解析</p>
            <div className="quick-actions">
              <button className="quick-action" onClick={() => { setInput('分析最近编码数据的分布特征'); handleSend() }}>
                分析数据分布
              </button>
              <button className="quick-action" onClick={() => { setInput('推荐一条高效的巡访路线'); handleSend() }}>
                推荐巡访路线
              </button>
              <button className="quick-action" onClick={() => { setInput('这些地址中有哪些可能编码错误？'); handleSend() }}>
                检测编码异常
              </button>
              <button className="quick-action" onClick={() => { setInput('帮我规划明天的出行路线'); handleSend() }}>
                规划出行路线
              </button>
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className="message">
            <div className={`message-avatar ${msg.role}`}>
              <i className={msg.role === 'user' ? 'fa-solid fa-user' : 'fa-solid fa-wand-magic-sparkles'} />
            </div>
            <div className="message-body">
              <div className="message-role">
                {msg.role === 'user' ? '你' : msg.role === 'system' ? '系统' : 'YaeLocus AI'}
              </div>
              {msg.reasoning && (
                <details className="reasoning-block">
                  <summary>💭 思考过程</summary>
                  <div className="reasoning-content">{msg.reasoning}</div>
                </details>
              )}
              {msg.content ? (
                <MessageContent content={msg.content} />
              ) : (streaming && messages.indexOf(msg) === messages.length - 1 ? (
                <div className="message-content">
                  <span className="typing-indicator">
                    <span></span><span></span><span></span>
                  </span>
                </div>
              ) : null)}
            </div>
          </div>
        ))}
      </div>

      {error && (
        <div className="alert alert-error" style={{ margin: '0 24px 12px' }}>
          {error}
        </div>
      )}

      {agentRound > 0 && streaming && (
        <div className="alert alert-info" style={{ margin: '0 24px 8px' }}>
          Agent 执行第 {agentRound}/{maxRounds} 轮...
        </div>
      )}

      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleTextareaInput}
            placeholder="输入你的问题，或 /new /compact /help ..."
            disabled={streaming}
            rows={1}
          />
          {streaming ? (
            <button onClick={handleCancel} className="chat-send-btn" title="停止">
              <Square size={16} />
            </button>
          ) : (
            <button onClick={handleSend} disabled={!input.trim()} className="chat-send-btn" title="发送">
              <Send size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
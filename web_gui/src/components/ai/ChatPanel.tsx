import { useState, useRef, useCallback } from 'react'
import { chatStream, executeCommand } from '../../lib/api'
import type { ChatMessage } from '../../lib/types'
import { Send, Square } from 'lucide-react'

const CMD_REGEX = /\[CMD\]\s*\n?(.*?)\n?\s*\[\/CMD\]/gs
const MAX_AGENT_ROUNDS = 4

export default function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState('')
  const [agentRound, setAgentRound] = useState(0)
  const streamContent = useRef('')
  const lastRenderRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleCancel = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
    setAgentRound(0)
  }, [])

  const executeCmd = useCallback(async (cmd: string): Promise<string> => {
    try {
      const result = await executeCommand(cmd)
      if (result.success) {
        return result.stdout || '成功'
      }
      return result.stderr || result.stdout || `失败 (exit: ${result.exit_code})`
    } catch (err: unknown) {
      return `执行失败: ${err instanceof Error ? err.message : String(err)}`
    }
  }, [])

  const handleSend = useCallback(() => {
    const trimmed = input.trim()
    if (!trimmed || streaming) return

    const userMsg: ChatMessage = { role: 'user', content: trimmed }
    const updatedMessages = [...messages, userMsg]
    setMessages([...updatedMessages, { role: 'assistant', content: '' }])
    setInput('')
    setError('')
    setStreaming(true)
    setAgentRound(0)
    streamContent.current = ''

    const controller = new AbortController()
    abortRef.current = controller

    runAgentLoop(trimmed, updatedMessages, controller.signal)
  }, [input, messages, streaming])

  const runAgentLoop = useCallback(async (
    prompt: string,
    contextMessages: ChatMessage[],
    signal: AbortSignal
  ) => {
    const context: ChatMessage[] = []
    for (const msg of contextMessages.slice(-30)) {
      if (msg.role === 'user' && msg.content) {
        context.push({ role: 'user', content: msg.content })
      } else if (msg.role === 'assistant' && msg.content) {
        context.push({ role: 'assistant', content: msg.content.slice(0, 800) })
      }
    }

    let currentPrompt = prompt
    let currentContext = context

    for (let round = 0; round < MAX_AGENT_ROUNDS; round++) {
      if (signal.aborted) break

      setAgentRound(round + 1)
      streamContent.current = ''

      let fullContent = ''

      try {
        await new Promise<void>((resolve) => {
          chatStream(
            currentPrompt,
            currentContext,
            (token) => {
              streamContent.current += token
              const now = Date.now()
              if (now - lastRenderRef.current >= 50) {
                lastRenderRef.current = now
                const content = streamContent.current
                setMessages(prev => {
                  const next = [...prev]
                  if (next.length > 0 && next[next.length - 1].role === 'assistant') {
                    next[next.length - 1] = { ...next[next.length - 1], content }
                  }
                  return next
                })
                scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
              }
            },
            () => {
              const content = streamContent.current
              setMessages(prev => {
                const next = [...prev]
                if (next.length > 0 && next[next.length - 1].role === 'assistant') {
                  next[next.length - 1] = { ...next[next.length - 1], content }
                }
                return next
              })
              resolve()
            },
            (err) => {
              setError(err)
              setStreaming(false)
              setAgentRound(0)
              resolve()
            },
            signal
          )
        })
      } catch {
        if (signal.aborted) break
      }

      fullContent = streamContent.current

      // Extract [CMD] blocks
      const cmds: string[] = []
      const visibleContent = fullContent.replace(CMD_REGEX, (_m: string, c: string) => {
        if (c.trim()) cmds.push(c.trim())
        return ''
      }).trim()

      if (visibleContent || fullContent) {
        // Update the message with visible content (commands stripped)
        setMessages(prev => {
          const next = [...prev]
          if (next.length > 0 && next[next.length - 1].role === 'assistant') {
            next[next.length - 1] = {
              ...next[next.length - 1],
              content: visibleContent || fullContent,
            }
          }
          return next
        })
      }

      if (cmds.length === 0) break

      // Execute commands
      let allOk = true
      let lastErr = ''
      let toolResults = ''

      for (const cmd of cmds) {
        if (signal.aborted) break
        const result = await executeCmd(cmd)
        toolResults += `命令: ${cmd}\n结果: ${result}\n\n`
        if (result.includes('失败') || result.includes('错误') || result.includes('Error')) {
          allOk = false
          lastErr = result
        }
      }

      if (!allOk) {
        setMessages(prev => [...prev, {
          role: 'assistant' as const,
          content: `⚠️ 命令执行出错:\n${lastErr}`,
        }])
      }

      // Feed results back for next agent round
      currentContext = [
        ...currentContext,
        { role: 'user', content: currentPrompt },
        { role: 'assistant', content: visibleContent || fullContent },
        { role: 'user', content: toolResults },
      ]
      currentPrompt = '请基于以上命令执行结果继续分析。如果已经得到最终答案，请直接给出结论。'
    }

    setStreaming(false)
    setAgentRound(0)
  }, [executeCmd])

  const handleQuickAction = useCallback((text: string) => {
    setInput(text)
    // Use setTimeout to ensure state is updated before sending
    setTimeout(() => {
      const userMsg: ChatMessage = { role: 'user', content: text }
      const updatedMessages = [...messages, userMsg]
      setMessages([...updatedMessages, { role: 'assistant', content: '' }])
      setError('')
      setStreaming(true)
      setAgentRound(0)
      streamContent.current = ''

      const controller = new AbortController()
      abortRef.current = controller

      runAgentLoop(text, updatedMessages, controller.signal)
    }, 0)
  }, [messages, runAgentLoop])

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
      <div ref={scrollRef} className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <div className="chat-welcome-icon">
              <i className="fa-solid fa-sparkles" />
            </div>
            <h3>YaeLocus AI 助手</h3>
            <p>基于地理数据的智能分析，支持数据洞察、路线规划和地址解析</p>
            <div className="quick-actions">
              <button className="quick-action" onClick={() => handleQuickAction('分析最近编码数据的分布特征')}>
                分析数据分布
              </button>
              <button className="quick-action" onClick={() => handleQuickAction('推荐一条高效的巡访路线')}>
                推荐巡访路线
              </button>
              <button className="quick-action" onClick={() => handleQuickAction('这些地址中有哪些可能编码错误？')}>
                检测编码异常
              </button>
              <button className="quick-action" onClick={() => handleQuickAction('帮我规划明天的出行路线')}>
                规划出行路线
              </button>
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className="message">
            <div className={`message-avatar ${msg.role}`}>
              <i className={msg.role === 'user' ? 'fa-solid fa-user' : 'fa-solid fa-sparkles'} />
            </div>
            <div className="message-body">
              <div className="message-role">{msg.role === 'user' ? '你' : 'YaeLocus AI'}</div>
              <div className="message-content">
                {msg.content || (streaming && i === messages.length - 1 ? (
                  <span className="typing-indicator">
                    <span></span><span></span><span></span>
                  </span>
                ) : '')}
              </div>
            </div>
          </div>
        ))}
      </div>

      {error && (
        <div className="alert alert-error" style={{ margin: '0 24px 12px' }}>
          {error}
        </div>
      )}

      {agentRound > 1 && streaming && (
        <div className="alert alert-info" style={{ margin: '0 24px 8px' }}>
          Agent 执行第 {agentRound} 轮...
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
            placeholder="输入你的问题，或描述你想分析的地理数据..."
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
import { useState, useRef, useCallback } from 'react'
import { chatStream } from '../../lib/api'
import type { ChatMessage } from '../../lib/types'
import { Send, Square } from 'lucide-react'

export default function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState('')
  const streamContent = useRef('')
  const lastRenderRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(() => {
    const trimmed = input.trim()
    if (!trimmed || streaming) return

    const userMsg: ChatMessage = { role: 'user', content: trimmed }
    const updatedMessages = [...messages, userMsg]
    setMessages([...updatedMessages, { role: 'assistant', content: '' }])
    setInput('')
    setError('')
    setStreaming(true)
    streamContent.current = ''

    const controller = new AbortController()
    abortRef.current = controller

    chatStream(
      trimmed,
      messages,
      (token) => {
        streamContent.current += token
        const now = Date.now()
        if (now - lastRenderRef.current >= 50) {
          lastRenderRef.current = now
          setMessages([...updatedMessages, { role: 'assistant', content: streamContent.current }])
          scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
        }
      },
      () => {
        setMessages([...updatedMessages, { role: 'assistant', content: streamContent.current }])
        setStreaming(false)
      },
      (err) => {
        setMessages(updatedMessages)
        setError(err)
        setStreaming(false)
      },
      controller.signal
    )
  }, [input, messages, streaming])

  const handleCancel = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
  }, [])

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

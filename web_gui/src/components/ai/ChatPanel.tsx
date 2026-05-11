import { useState, useRef, useCallback } from 'react'
import { chatStream } from '../../lib/api'
import type { ChatMessage } from '../../lib/types'
import { Send, Loader2, Bot, User } from 'lucide-react'

export default function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState('')
  const streamContent = useRef('')
  const lastRenderRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

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
        // Throttle re-renders to ~20fps，避免每个 token 都全量 re-render
        const now = Date.now()
        if (now - lastRenderRef.current >= 50) {
          lastRenderRef.current = now
          setMessages([...updatedMessages, { role: 'assistant', content: streamContent.current }])
          scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
        }
      },
      () => {
        // 最终渲染确保所有 token 显示
        setMessages([...updatedMessages, { role: 'assistant', content: streamContent.current }])
        setStreaming(false)
      },
      (err) => {
        setError(err)
        setStreaming(false)
      },
      controller.signal
    )
  }, [input, messages, streaming])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div style={{ background: 'rgba(43,18,0,0.02)', borderRadius: 8, padding: 28 }}>
      <h3 style={{ fontSize: 20, fontWeight: 600, color: '#1c1c1c', marginBottom: 4 }}>AI 对话</h3>
      <p style={{ color: 'rgba(20,20,19,0.65)', fontSize: 14, marginBottom: 16 }}>
        基于 LLM 的智能助手，可分析数据、回答地理编码相关问题
      </p>

      <div
        ref={scrollRef}
        style={{
          height: 400, overflow: 'auto', border: '1px solid #eae8e7', borderRadius: 8,
          padding: 16, marginBottom: 16, background: '#fff',
        }}
      >
        {messages.length === 0 && (
          <div style={{ padding: 32, textAlign: 'center', color: '#888' }}>
            <Bot size={48} style={{ color: '#ccc', marginBottom: 12 }} />
            <div style={{ fontSize: 15, marginBottom: 4 }}>开始对话</div>
            <div style={{ fontSize: 13, color: '#aaa' }}>输入消息与 AI 助手交流</div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              marginBottom: 12,
              display: 'flex',
              gap: 8,
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            {msg.role === 'assistant' && (
              <Bot size={18} style={{ color: '#ff9d4d', marginTop: 4, flexShrink: 0 }} />
            )}
            <div
              style={{
                maxWidth: '80%',
                padding: '10px 14px',
                borderRadius: 8,
                background: msg.role === 'user' ? '#ff9d4d' : '#f5f7fa',
                color: msg.role === 'user' ? 'rgba(20,20,19,0.88)' : '#1c1c1c',
                fontSize: 14,
                lineHeight: 1.5,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {msg.content || (streaming && i === messages.length - 1 ? (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  思考中<Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
                </span>
              ) : '')}
            </div>
            {msg.role === 'user' && (
              <User size={18} style={{ color: '#1a73e8', marginTop: 4, flexShrink: 0 }} />
            )}
          </div>
        ))}
      </div>

      {error && (
        <div style={{ marginBottom: 12, padding: '8px 12px', background: '#fce8e6', borderRadius: 8, color: '#d93025', fontSize: 13 }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息，按 Enter 发送..."
          disabled={streaming}
          rows={2}
          style={{
            flex: 1, padding: '10px 14px', border: '1.5px solid #eae8e7', borderRadius: 8,
            fontSize: 14, outline: 'none', fontFamily: 'inherit', resize: 'none',
          }}
        />
        <button
          onClick={handleSend}
          disabled={streaming || !input.trim()}
          style={{
            padding: '10px 20px', background: streaming ? '#ccc' : '#ff9d4d', color: 'rgba(20,20,19,0.88)',
            border: 'none', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: streaming ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', gap: 6, alignSelf: 'flex-end',
          }}
        >
          {streaming ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Send size={16} />}
          发送
        </button>
      </div>
    </div>
  )
}

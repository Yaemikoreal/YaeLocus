import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { ChatMessage } from './types'

let msgCounter = 0
function nextId(): string {
  return `msg-${++msgCounter}-${Date.now()}`
}

interface ChatState {
  currentSessionId: string
  sessions: Record<string, { id: string; title: string; createdAt: number; updatedAt: number }>
  messages: Record<string, ChatMessage[]>

  getCurrentMessages: () => ChatMessage[]
  addMessage: (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => string
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void
  clearCurrentSession: () => void
  newSession: () => string
  compactCurrentSession: () => void
  exportCurrentSession: () => string
  setSessionId: (id: string) => void
}

const MAX_MESSAGES_PER_SESSION = 200

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      currentSessionId: '',
      sessions: {},
      messages: {},

      getCurrentMessages: () => {
        const state = get()
        return state.messages[state.currentSessionId] || []
      },

      addMessage: (msg) => {
        const id = nextId()
        const fullMsg: ChatMessage = { ...msg, id, timestamp: Date.now() }
        const state = get()
        const sid = state.currentSessionId
        const session = state.sessions[sid]
        if (!session) return id

        const existing = state.messages[sid] || []
        const updated = [...existing, fullMsg].slice(-MAX_MESSAGES_PER_SESSION)

        set({
          messages: { ...state.messages, [sid]: updated },
          sessions: {
            ...state.sessions,
            [sid]: { ...session, updatedAt: Date.now() },
          },
        })
        return id
      },

      updateMessage: (id, updates) => {
        const state = get()
        const sid = state.currentSessionId
        const existing = state.messages[sid] || []
        const messages = existing.map((m: ChatMessage) =>
          m.id === id ? { ...m, ...updates } : m
        )
        set({ messages: { ...state.messages, [sid]: messages } })
      },

      clearCurrentSession: () => {
        const newId = crypto.randomUUID()
        set((state) => ({
          currentSessionId: newId,
          sessions: {
            ...state.sessions,
            [newId]: { id: newId, title: '', createdAt: Date.now(), updatedAt: Date.now() },
          },
          messages: { ...state.messages },
        }))
      },

      newSession: () => {
        const newId = crypto.randomUUID()
        set((state) => ({
          currentSessionId: newId,
          sessions: {
            ...state.sessions,
            [newId]: { id: newId, title: '', createdAt: Date.now(), updatedAt: Date.now() },
          },
          messages: { ...state.messages },
        }))
        return newId
      },

      compactCurrentSession: () => {
        const state = get()
        const sid = state.currentSessionId
        const existing = state.messages[sid] || []
        const messages = existing.slice(-10)
        set({ messages: { ...state.messages, [sid]: messages } })
      },

      exportCurrentSession: () => {
        const state = get()
        const sid = state.currentSessionId
        const messages = state.messages[sid] || []
        return messages
          .map((m: ChatMessage) => {
            let text = `**${m.role}**`
            if (m.reasoning) text += `\n> ${m.reasoning}`
            text += `\n${m.content}`
            return text
          })
          .join('\n\n---\n\n')
      },

      setSessionId: (id: string) => {
        set({ currentSessionId: id })
      },
    }),
    {
      name: 'yaelocus-chat-sessions',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        currentSessionId: state.currentSessionId,
        sessions: Object.fromEntries(
          Object.entries(state.sessions)
            .sort(([, a], [, b]) => b.updatedAt - a.updatedAt)
            .slice(0, 10)
        ),
        messages: (() => {
        const filtered: Record<string, ChatMessage[]> = {}
        for (const [k, v] of Object.entries(state.messages)) {
          if (v.length > 0) {
            filtered[k] = v.slice(-50)
          }
        }
        return filtered
      })(),
      }),
      onRehydrateStorage: () => {
        return (state) => {
          if (state) {
            for (const msgs of Object.values(state.messages || {})) {
              for (const m of msgs) {
                const match = m.id?.match(/^msg-(\d+)-/)
                if (match) msgCounter = Math.max(msgCounter, parseInt(match[1], 10))
              }
            }
          }
        }
      },
    }
  )
)
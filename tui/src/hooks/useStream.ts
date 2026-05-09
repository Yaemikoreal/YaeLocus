/**
 * SSE 流式接收 — 从 Python /api/chat/stream 逐 token 读取
 */

import { useState, useCallback, useRef } from 'react';

export function useStream() {
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  /** 开始流式接收，对每个 token 调用 onToken，完成后调用 onDone */
  const startStream = useCallback(async (
    streamUrl: string,
    postBody: Record<string, unknown>,
    onToken: (token: string) => void,
    onDone: () => void,
    onError: (err: Error) => void,
  ) => {
    const controller = new AbortController();
    abortRef.current = controller;
    setStreaming(true);

    try {
      const res = await fetch(streamUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(postBody),
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API error ${res.status}: ${text}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;
          const data = trimmed.slice(6);
          if (data === '[DONE]') {
            setStreaming(false);
            onDone();
            return;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.token) onToken(parsed.token);
            if (parsed.error) onError(new Error(parsed.error));
          } catch {
            // 跳过非 JSON 行
          }
        }
      }
      setStreaming(false);
      onDone();
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setStreaming(false);
      onError(err instanceof Error ? err : new Error(String(err)));
    }
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setStreaming(false);
  }, []);

  return { streaming, startStream, cancel };
}

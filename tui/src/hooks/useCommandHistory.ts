/**
 * 命令行历史 — 类似 bash 的上下键历史导航
 */

import { useState, useCallback, useRef } from 'react';

const MAX_HISTORY = 100;

export function useCommandHistory() {
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const preHistoryRef = useRef<string>('');

  const addToHistory = useCallback((cmd: string) => {
    const trimmed = cmd.trim();
    if (!trimmed) return;
    setHistory(prev => {
      // 去重：不添加连续相同的命令
      if (prev.length > 0 && prev[prev.length - 1] === trimmed) return prev;
      const next = [...prev, trimmed];
      if (next.length > MAX_HISTORY) next.shift();
      return next;
    });
    setHistoryIndex(-1);
  }, []);

  /** 上一条历史 */
  const historyUp = useCallback((currentText: string): string => {
    if (history.length === 0) return currentText;
    const newIndex = historyIndex === -1
      ? history.length - 1
      : Math.max(0, historyIndex - 1);
    if (historyIndex === -1) {
      preHistoryRef.current = currentText;
    }
    setHistoryIndex(newIndex);
    return history[newIndex];
  }, [history, historyIndex]);

  /** 下一条历史 */
  const historyDown = useCallback((): string => {
    if (historyIndex === -1) return '';
    const newIndex = historyIndex + 1;
    if (newIndex >= history.length) {
      setHistoryIndex(-1);
      return preHistoryRef.current;
    }
    setHistoryIndex(newIndex);
    return history[newIndex];
  }, [history, historyIndex]);

  return { history, historyIndex, addToHistory, historyUp, historyDown };
}

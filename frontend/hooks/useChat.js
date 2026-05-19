import { useState, useEffect, useRef } from 'react';
import { fetchWithAuth } from '../lib/auth';

export function useChat() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [thinkMode, setThinkMode] = useState(false);

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
  }, []);

  // Load messages when active session changes
  useEffect(() => {
    if (activeSessionId) {
      setMessages([]);
      loadMessages(activeSessionId);
    } else {
      setMessages([]);
    }
  }, [activeSessionId]);

  const loadSessions = async () => {
    try {
      const res = await fetchWithAuth('/api/v1/chat/sessions');
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
        if (data.length > 0 && !activeSessionId) {
          setActiveSessionId(data[0].id);
        }
      }
    } catch (e) {
      console.error("Failed to load sessions", e);
    }
  };

  const loadMessages = async (sessionId) => {
    try {
      const res = await fetchWithAuth(`/api/v1/chat/sessions/${sessionId}/messages`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      }
    } catch (e) {
      console.error("Failed to load messages", e);
    }
  };

  const createSession = async () => {
    try {
      const res = await fetchWithAuth('/api/v1/chat/sessions', { method: 'POST' });
      if (res.ok) {
        const newSession = await res.json();
        setSessions([newSession, ...sessions]);
        setActiveSessionId(newSession.id);
        return newSession;
      }
    } catch (e) {
      console.error("Failed to create session", e);
    }
    return null;
  };

  const deleteSession = async (sessionId) => {
    try {
      const res = await fetchWithAuth(`/api/v1/chat/sessions/${sessionId}`, { method: 'DELETE' });
      if (res.ok) {
        setSessions(sessions.filter(s => s.id !== sessionId));
        if (activeSessionId === sessionId) {
          setActiveSessionId(sessions.find(s => s.id !== sessionId)?.id || null);
        }
      }
    } catch (e) {
      console.error("Failed to delete session", e);
    }
  };

  const sendMessage = async (content) => {
    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      const newSession = await createSession();
      if (!newSession) return;
      currentSessionId = newSession.id;
    }

    const userMsg = { role: 'user', content, id: Date.now() };
    const botMsg = { role: 'assistant', content: '', think_content: '', context_article_ids: [], id: Date.now() + 1 };
    
    setMessages(prev => [...prev, userMsg, botMsg]);
    setIsLoading(true);

    try {
      const res = await fetchWithAuth(`/api/v1/chat/sessions/${currentSessionId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content, think_mode: thinkMode })
      });

      if (!res.ok) throw new Error("Failed to send message");

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      
      let botContent = '';
      let thinkContent = '';
      let contextIds = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ') && line !== 'data: [DONE]') {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'content') {
                botContent += data.text;
              } else if (data.type === 'think') {
                thinkContent += data.text;
              } else if (data.type === 'context') {
                contextIds = data.article_ids;
              } else if (data.type === 'error') {
                botContent += `\n[Error: ${data.text}]`;
              }
              
              setMessages(prev => {
                const newMsgs = [...prev];
                newMsgs[newMsgs.length - 1] = {
                  ...newMsgs[newMsgs.length - 1],
                  content: botContent,
                  think_content: thinkContent,
                  context_article_ids: contextIds
                };
                return newMsgs;
              });
            } catch (e) {
              console.error("Error parsing chunk", e, line);
            }
          }
        }
      }
      
      // Reload sessions to update title if it changed
      loadSessions();
      
    } catch (e) {
      console.error(e);
      setMessages(prev => {
        const newMsgs = [...prev];
        newMsgs[newMsgs.length - 1] = {
          ...newMsgs[newMsgs.length - 1],
          content: "发生错误，请稍后再试。"
        };
        return newMsgs;
      });
    } finally {
      setIsLoading(false);
    }
  };

  return {
    sessions,
    activeSessionId,
    setActiveSessionId,
    messages,
    isLoading,
    thinkMode,
    setThinkMode,
    sendMessage,
    createSession,
    deleteSession
  };
}

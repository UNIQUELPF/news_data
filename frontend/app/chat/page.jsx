"use client";

import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useChat } from "../../hooks/useChat";
import SidebarNav from "../../components/SidebarNav";
import AppHeader from "../../components/AppHeader";
import ArticleDetail from "../../components/ArticleDetail";
import { useArticleSearch } from "../../hooks/useArticleSearch";
import "../globals.css";

function ChatSidebar({ sessions, activeSessionId, onSelect, onNew, onDelete, isCollapsed, onToggleCollapse, messages }) {
  const isNewDisabled = sessions.length > 0 && (!messages || !messages.some(m => m.role === 'user'));

  if (isCollapsed) {
    return (
      <div style={{ width: '60px', background: '#0e2c4f', borderRight: '1px solid rgba(255,255,255,0.1)', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '20px 0' }}>
        <button onClick={onToggleCollapse} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', marginBottom: '20px' }}>
          ▶
        </button>
        <button 
          onClick={onNew} 
          disabled={isNewDisabled}
          title={isNewDisabled ? "当前会话为空，请先发送消息" : "新建会话"}
          style={{ 
            background: isNewDisabled ? 'rgba(36, 87, 214, 0.4)' : '#2457d6', 
            border: 'none', 
            color: isNewDisabled ? 'rgba(255, 255, 255, 0.4)' : '#fff', 
            cursor: isNewDisabled ? 'not-allowed' : 'pointer', 
            borderRadius: '50%', 
            width: '36px', 
            height: '36px', 
            fontSize: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.2s'
          }}
        >
          +
        </button>
      </div>
    );
  }

  return (
    <div style={{ width: '260px', background: '#0e2c4f', borderRight: '1px solid rgba(255,255,255,0.1)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <h3 style={{ margin: 0, color: '#fff', fontSize: '16px' }}>历史会话</h3>
        <button onClick={onToggleCollapse} style={{ background: 'none', border: 'none', color: '#6f8298', cursor: 'pointer' }}>
          ◀
        </button>
      </div>
      <div style={{ padding: '20px' }}>
        <button 
          onClick={onNew} 
          disabled={isNewDisabled}
          title={isNewDisabled ? "当前会话为空，请先发送消息" : "新建会话"}
          style={{ 
            width: '100%', 
            padding: '12px', 
            background: isNewDisabled ? 'rgba(36, 87, 214, 0.4)' : '#2457d6', 
            color: isNewDisabled ? 'rgba(255, 255, 255, 0.4)' : '#fff', 
            border: 'none', 
            borderRadius: '8px', 
            cursor: isNewDisabled ? 'not-allowed' : 'pointer', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            gap: '8px',
            transition: 'all 0.2s'
          }}
        >
          <span>+</span> 新会话
        </button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 10px' }}>
        {sessions.map(s => (
          <div 
            key={s.id} 
            onClick={() => onSelect(s.id)}
            style={{ 
              padding: '12px', 
              margin: '0 10px 8px', 
              borderRadius: '8px', 
              cursor: 'pointer',
              background: activeSessionId === s.id ? 'rgba(255,255,255,0.1)' : 'transparent',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              color: activeSessionId === s.id ? '#fff' : '#6f8298'
            }}
          >
            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}>{s.title}</span>
            <button onClick={(e) => { e.stopPropagation(); onDelete(s.id); }} style={{ background: 'none', border: 'none', color: '#6f8298', cursor: 'pointer', padding: '0 4px' }}>
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function CitationLink({ id, onOpen }) {
  return (
    <span 
      onClick={() => onOpen(id)}
      style={{ 
        color: '#efc94c', 
        cursor: 'pointer', 
        fontWeight: 'bold',
        padding: '0 4px',
        textDecoration: 'underline'
      }}
    >
      [文章 {id}]
    </span>
  );
}

function ChatMessage({ msg, onOpenArticle }) {
  const isUser = msg.role === 'user';
  

  return (
    <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', flexDirection: isUser ? 'row-reverse' : 'row' }}>
      <div style={{ 
        width: '40px', height: '40px', borderRadius: '50%', flexShrink: 0,
        background: isUser ? '#2457d6' : '#18324b',
        display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '20px'
      }}>
        {isUser ? 'U' : '🤖'}
      </div>
      <div style={{ maxWidth: '70%', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: isUser ? 'flex-end' : 'flex-start' }}>
        {msg.think_content && (
          <div style={{ 
            padding: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '12px', color: '#8b9eb3', fontSize: '14px',
            borderLeft: '4px solid #efc94c', whiteSpace: 'pre-wrap'
          }}>
            <div style={{ fontWeight: 'bold', marginBottom: '8px', color: '#a0aec0' }}>思考过程：</div>
            {msg.think_content}
          </div>
        )}
        <div style={{ 
          padding: '16px', borderRadius: '12px',
          background: isUser ? '#2457d6' : '#18324b', color: '#fff',
          borderTopRightRadius: isUser ? '0' : '12px',
          borderTopLeftRadius: isUser ? '12px' : '0',
          lineHeight: '1.6',
          width: '100%'
        }} className="markdown-body">
          {isUser ? (
            <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
          ) : (
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({node, href, children, ...props}) => {
                  if (href && href.startsWith('#citation-')) {
                    const id = href.replace('#citation-', '');
                    return <CitationLink id={id} onOpen={onOpenArticle} />;
                  }
                  return <a href={href} target="_blank" rel="noopener noreferrer" {...props}>{children}</a>;
                }
              }}
            >
              {msg.content.replace(/\[(?:根据)?参考(?:资料|来源|文献)?\s*[:：]?\s*(\d+)\]|\[文章\s*[:：]?\s*(\d+)\]/g, (match, p1, p2) => {
                const id = p1 || p2;
                return `[文章 ${id}](#citation-${id})`;
              })}
            </ReactMarkdown>
          )}
        </div>
        {msg.context_article_ids && msg.context_article_ids.length > 0 && (
          <div style={{ fontSize: '12px', color: '#6f8298', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            参考来源: 
            {msg.context_article_ids.map(id => (
              <span 
                key={id} 
                onClick={() => onOpenArticle(id)} 
                style={{ color: '#efc94c', cursor: 'pointer', textDecoration: 'underline' }}
              >
                [文章 {id}]
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ChatInput({ input, setInput, handleKeyDown, isLoading, thinkMode, setThinkMode, handleSubmit }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [input]);

  return (
    <div style={{ background: '#18324b', borderRadius: '16px', padding: '12px 16px', border: '1px solid rgba(255,255,255,0.1)', display: 'flex', flexDirection: 'column', gap: '8px', width: '100%', boxShadow: '0 8px 32px rgba(0,0,0,0.15)' }}>
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="发送消息..."
        disabled={isLoading}
        style={{ 
          width: '100%', background: 'transparent', border: 'none', color: '#fff', fontSize: '16px', 
          resize: 'none', outline: 'none', maxHeight: '200px', minHeight: '44px', fontFamily: 'inherit'
        }}
        rows={1}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '16px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: thinkMode ? '#efc94c' : '#6f8298', cursor: 'pointer', fontSize: '14px' }}>
            <input 
              type="checkbox" 
              checked={thinkMode} 
              onChange={(e) => setThinkMode(e.target.checked)} 
              style={{ display: 'none' }}
            />
            <div style={{ width: '32px', height: '18px', background: thinkMode ? '#efc94c' : 'rgba(255,255,255,0.2)', borderRadius: '10px', position: 'relative', transition: 'all 0.3s' }}>
              <div style={{ width: '14px', height: '14px', background: '#fff', borderRadius: '50%', position: 'absolute', top: '2px', left: thinkMode ? '16px' : '2px', transition: 'all 0.3s' }} />
            </div>
            深度思考
          </label>
        </div>
        <button 
          onClick={handleSubmit} 
          disabled={!input.trim() || isLoading}
          style={{ 
            background: input.trim() && !isLoading ? '#2457d6' : 'rgba(255,255,255,0.1)', 
            color: input.trim() && !isLoading ? '#fff' : '#6f8298',
            border: 'none', borderRadius: '8px', padding: '8px 16px', cursor: input.trim() && !isLoading ? 'pointer' : 'not-allowed',
            fontWeight: 'bold',
            transition: 'all 0.2s'
          }}
        >
          发送
        </button>
      </div>
    </div>
  );
}


import { useRouter } from "next/navigation";
import { getToken } from "../../lib/auth";

export default function ChatPage() {
  const router = useRouter();
  const [isAuthChecking, setIsAuthChecking] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
    } else {
      setIsAuthChecking(false);
    }
  }, [router]);

  const {
    sessions, activeSessionId, setActiveSessionId,
    messages, isLoading, thinkMode, setThinkMode,
    sendMessage, createSession, deleteSession
  } = useChat();

  const {
    selectedArticle,
    selectedArticleLoading,
    openArticle,
    setSelectedArticle
  } = useArticleSearch();

  const [input, setInput] = useState('');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    sendMessage(input);
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (isAuthChecking) {
    return <div style={{ background: '#0e2c4f', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>加载中...</div>;
  }

  return (
    <main className="shell" style={{ height: '100vh', overflow: 'hidden' }}>
      <AppHeader title="政经小助手" subtitle="基于全球政治经济数据库的智能问答助手" />
      
      <div className="main-grid" style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
        <SidebarNav />
        
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <ChatSidebar 
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelect={setActiveSessionId}
            onNew={createSession}
            onDelete={deleteSession}
            isCollapsed={isSidebarCollapsed}
            onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            messages={messages}
          />
          
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#091e36', position: 'relative', overflow: 'hidden' }}>
            
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
              {messages.length === 0 ? (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 10%', minHeight: '100%' }}>
                  <div style={{ width: '100%', maxWidth: '720px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '24px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '20px', marginBottom: '8px' }}>
                      <span style={{ fontSize: '64px', filter: 'drop-shadow(0 0 16px rgba(36,87,214,0.3))' }}>🤖</span>
                      <h1 style={{ margin: 0, color: '#fff', fontSize: '36px', fontWeight: 'bold', letterSpacing: '1px' }}>我是政经小助手</h1>
                    </div>
                    <p style={{ color: '#8b9eb3', fontSize: '18px', margin: '0 0 24px 0', textAlign: 'center', lineHeight: '1.6', maxWidth: '500px' }}>
                      您可以问我关于全球政治、经济、央行政策等任何问题。
                    </p>
                    <ChatInput 
                      input={input}
                      setInput={setInput}
                      handleKeyDown={handleKeyDown}
                      isLoading={isLoading}
                      thinkMode={thinkMode}
                      setThinkMode={setThinkMode}
                      handleSubmit={handleSubmit}
                    />
                    <div style={{ textAlign: 'center', color: '#4a5568', fontSize: '12px', marginTop: '16px' }}>
                      内容由 AI 生成，可能存在错误，请核实参考资料。
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ flex: 1, overflowY: 'auto', padding: '40px 10%' }}>
                  {messages.map(msg => <ChatMessage key={msg.id} msg={msg} onOpenArticle={openArticle} />)}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Article Detail Drawer */}
            {selectedArticle && (
              <div style={{ 
                position: 'absolute', top: 0, right: 0, width: '50%', height: '100%', 
                background: '#091e36', borderLeft: '1px solid rgba(255,255,255,0.1)', 
                zIndex: 100, display: 'flex', flexDirection: 'column', boxShadow: '-10px 0 30px rgba(0,0,0,0.5)'
              }}>
                <div style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                  <h3 style={{ margin: 0, color: '#fff' }}>参考资料详情</h3>
                  <button 
                    onClick={() => setSelectedArticle(null)}
                    style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontSize: '24px' }}
                  >
                    ×
                  </button>
                </div>
                <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
                  <ArticleDetail 
                    articleData={selectedArticle} 
                    loading={selectedArticleLoading} 
                    onOpenArticle={openArticle} 
                  />
                </div>
              </div>
            )}

            {messages.length > 0 && (
              <div style={{ padding: '20px 10%', background: 'linear-gradient(180deg, rgba(9,30,54,0) 0%, #091e36 20%)', zIndex: 10 }}>
                <ChatInput 
                  input={input}
                  setInput={setInput}
                  handleKeyDown={handleKeyDown}
                  isLoading={isLoading}
                  thinkMode={thinkMode}
                  setThinkMode={setThinkMode}
                  handleSubmit={handleSubmit}
                />
                <div style={{ textAlign: 'center', color: '#4a5568', fontSize: '12px', marginTop: '12px' }}>
                  内容由 AI 生成，可能存在错误，请核实参考资料。
                </div>
              </div>
            )}
            
          </div>
        </div>
      </div>
    </main>
  );
}

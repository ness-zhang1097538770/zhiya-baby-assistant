"use client";

import {
  CircleAlert,
  History,
  LoaderCircle,
  MessageCircleHeart,
  Plus,
  RefreshCw,
  SendHorizonal,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChildDialog } from "@/components/ChildDialog";
import { api } from "@/lib/api";
import { track } from "@/lib/analytics";
import { ageLabel, formatTime } from "@/lib/format";
import type { AppError, Child, ConversationSummary, QAMessage } from "@/lib/types";
import { AnswerCard } from "./AnswerCard";

// 高频问题模板库（参考 ai-muying 的“一键套用”思路）
const QUESTION_TEMPLATES = [
  { tag: "喂养辅食", items: ["8 个月辅食加什么？", "辅食什么时候开始加？", "宝宝挑食不爱吃饭怎么办？", "转奶要注意什么？"] },
  { tag: "睡眠作息", items: ["宝宝夜里总醒怎么办？", "怎么帮宝宝建立规律作息？", "宝宝不肯自己睡怎么办？"] },
  { tag: "健康护理", items: ["宝宝发烧怎么办？", "宝宝拉肚子怎么护理？", "宝宝便秘怎么办？", "宝宝长牙怎么护理？"] },
  { tag: "发育早教", items: ["2-3 岁怎么立规矩？", "孩子不爱说话怎么办？", "宝宝多大可以看屏幕？"] },
  { tag: "疫苗", items: ["宝宝疫苗时间表是什么？", "打疫苗后发烧怎么办？"] },
];

export function AskPage() {
  const [children, setChildren] = useState<Child[]>([]);
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<QAMessage[]>([]);
  const [phase, setPhase] = useState<"loading" | "no-child" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [streamError, setStreamError] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const selected = children.find((child) => child.id === selectedChildId) ?? null;

  const loadHistory = useCallback(async (conversationId: number) => {
    try {
      const result = await api.getConversation(conversationId);
      setCurrentConversationId(result.conversation_id);
      setMessages(result.messages);
      setStreamText("");
      setStreamError("");
      setPhase("ready");
    } catch {
      setCurrentConversationId(conversationId);
      setMessages([]);
      setPhase("ready");
    }
  }, []);

  const loadConversations = useCallback(
    async (childId: number) => {
      try {
        const result = await api.listConversations(childId);
        setConversations(result.items);
        if (result.items.length === 0) {
          setCurrentConversationId(null);
          setMessages([]);
          setStreamText("");
          setStreamError("");
          setPhase("ready");
          return;
        }
        await loadHistory(result.items[0].id);
      } catch {
        setConversations([]);
        setCurrentConversationId(null);
        setMessages([]);
        setPhase("ready");
      }
    },
    [loadHistory],
  );

  const loadChildren = useCallback(
    async (preferredId?: number) => {
      setPhase("loading");
      setError("");
      try {
        const result = await api.listChildren();
        setChildren(result.items);
        const stored = Number(window.localStorage.getItem("kids-mind-child-id"));
        const validStored = result.items.some((child) => child.id === stored) ? stored : undefined;
        const targetId = preferredId ?? validStored ?? result.items[0]?.id;
        if (!targetId) {
          setSelectedChildId(null);
          setConversations([]);
          setMessages([]);
          setPhase("no-child");
          return;
        }
        setSelectedChildId(targetId);
        window.localStorage.setItem("kids-mind-child-id", String(targetId));
        await loadConversations(targetId);
      } catch (caught) {
        setError((caught as AppError).userMessage ?? "问育儿页暂时加载失败。");
        setPhase("error");
      }
    },
    [loadConversations],
  );

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) {
      window.history.replaceState({}, "", window.location.pathname);
      window.setTimeout(() => setInput(q), 0);
    }
    const timer = window.setTimeout(() => void loadChildren(), 0);
    return () => window.clearTimeout(timer);
  }, [loadChildren]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streamText, streaming]);

  async function runQuestion(question: string, conversationId: number | null) {
    setStreaming(true);
    setStreamText("");
    setStreamError("");
    try {
      await api.askQuestion({ child_id: selectedChildId as number, question, conversation_id: conversationId }, (event) => {
        if (event.type === "chunk") {
          setStreamText((prev) => prev + event.text);
        } else if (event.type === "done") {
          const data = event.data;
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: data.answer, risk_level: data.risk_level, sources: data.sources, followup_question: data.followup_question },
          ]);
          setCurrentConversationId(data.conversation_id);
          setStreamText("");
          setStreaming(false);
          void api
            .listConversations(selectedChildId as number)
            .then((result) => setConversations(result.items))
            .catch(() => {});
        } else if (event.type === "error") {
          if (typeof event.conversation_id === "number") setCurrentConversationId(event.conversation_id);
          setStreamError(event.message);
          setStreaming(false);
        }
      });
    } catch (caught) {
      setStreamError((caught as AppError).userMessage ?? "生成失败，请稍后重试。");
      setStreaming(false);
    }
  }

  async function submit(event?: React.FormEvent) {
    event?.preventDefault();
    const question = input.trim();
    if (!question || !selectedChildId || sending) return;
    setInput("");
    setLastQuestion(question);
    void track("qa_ask");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setSending(true);
    await runQuestion(question, currentConversationId);
    setSending(false);
  }

  async function resend() {
    if (!lastQuestion || !selectedChildId || sending) return;
    setSending(true);
    await runQuestion(lastQuestion, currentConversationId);
    setSending(false);
  }

  function changeChild(id: number) {
    window.localStorage.setItem("kids-mind-child-id", String(id));
    setSelectedChildId(id);
    void loadConversations(id);
  }

  function newConversation() {
    setCurrentConversationId(null);
    setMessages([]);
    setStreamText("");
    setStreamError("");
    setLastQuestion("");
  }

  async function deleteConversation(id: number) {
    if (!window.confirm("确定删除这条会话吗？删除后无法恢复。")) return;
    try {
      await api.deleteConversation(id);
      if (id === currentConversationId) newConversation();
      if (selectedChildId) await loadConversations(selectedChildId);
    } catch (caught) {
      setStreamError((caught as AppError).userMessage ?? "删除失败，请稍后重试。");
    }
  }

  async function deleteAllConversations() {
    if (!selectedChildId) return;
    if (!window.confirm("确定删除该孩子的全部历史会话吗？此操作不可恢复。")) return;
    try {
      await api.deleteAllConversations(selectedChildId);
      newConversation();
      await loadConversations(selectedChildId);
    } catch (caught) {
      setStreamError((caught as AppError).userMessage ?? "删除失败，请稍后重试。");
    }
  }

  if (phase === "loading") {
    return (
      <div className="page-state" role="status">
        <LoaderCircle className="spin" size={30} />
        <strong>正在读取孩子档案…</strong>
        <span>历史会话和育儿建议很快就好</span>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="page-state error-state">
        <CircleAlert size={30} />
        <strong>暂时没能连上服务</strong>
        <span>{error}</span>
        <button className="button secondary" onClick={() => void loadChildren()}>
          <RefreshCw size={17} />重新连接
        </button>
      </div>
    );
  }

  if (!selected) {
    return (
      <div className="empty-home">
        <div className="empty-visual">
          <span className="orbit one" />
          <span className="orbit two" />
          <MessageCircleHeart size={44} />
        </div>
        <span className="eyebrow">问育儿</span>
        <h1>先建立孩子的档案，<br />建议才更贴合月龄</h1>
        <p>建档后，育儿回答会自动带上月龄、喂养方式和过敏史。</p>
        <button className="button primary large" onClick={() => setDialogOpen(true)}>
          <Plus size={19} />建立成长档案
        </button>
        {dialogOpen && (
          <ChildDialog onClose={() => setDialogOpen(false)} onCreated={(child) => { setDialogOpen(false); void loadChildren(child.id); }} />
        )}
      </div>
    );
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="ask-page">
      <header className="ask-topbar">
        <div>
          <p className="kicker">问育儿</p>
          <h1>向 <em>{selected.nickname}</em> 的育儿助手提问</h1>
        </div>
        <div className="ask-child-picker">
          <select value={selected.id} onChange={(event) => changeChild(Number(event.target.value))} aria-label="切换孩子">
            {children.map((child) => (
              <option key={child.id} value={child.id}>{child.nickname} · {ageLabel(child.birth_date)}</option>
            ))}
          </select>
          <button className="add-child" onClick={() => setDialogOpen(true)} aria-label="添加孩子"><Plus size={18} /></button>
        </div>
      </header>

      <div className="ask-layout">
        <aside className="conv-panel" aria-label="历史会话">
          <div className="conv-head">
            <span className="conv-title"><History size={15} /> 历史会话</span>
            <div className="conv-head-actions">
              {conversations.length ? (
                <button className="conv-new danger" onClick={() => void deleteAllConversations()}><Trash2 size={14} /> 删除全部</button>
              ) : null}
              <button className="conv-new" onClick={newConversation}><Plus size={15} /> 新提问</button>
            </div>
          </div>
          {conversations.length ? (
            <div className="conv-list">
              {conversations.map((conversation) => (
                <div key={conversation.id} className={conversation.id === currentConversationId ? "conv-row active" : "conv-row"}>
                  <button
                    className="conv-item"
                    onClick={() => void loadHistory(conversation.id)}
                  >
                    <strong>{conversation.title}</strong>
                    <small>{formatTime(conversation.updated_at || conversation.created_at)}</small>
                  </button>
                  <button className="conv-delete" onClick={() => void deleteConversation(conversation.id)} aria-label="删除会话"><Trash2 size={14} /></button>
                </div>
              ))}
            </div>
          ) : (
            <div className="conv-empty"><Sparkles size={18} /><span>还没有提问记录</span></div>
          )}
        </aside>

        <section className="chat-panel">
          <div className="mobile-conv-bar">
            <select
              className="conv-select"
              value={currentConversationId ?? 0}
              onChange={(event) => {
                const value = Number(event.target.value);
                if (value === 0) newConversation();
                else void loadHistory(value);
              }}
              aria-label="切换历史会话"
            >
              <option value={0}>＋ 新提问</option>
              {conversations.map((conversation) => (
                <option key={conversation.id} value={conversation.id}>{conversation.title}</option>
              ))}
            </select>
            {conversations.length ? (
              <button className="conv-delete-mobile" onClick={() => void deleteAllConversations()} aria-label="删除全部会话"><Trash2 size={16} /></button>
            ) : null}
          </div>

          <div className="message-list">
            {!hasMessages && !streaming ? (
              <div className="chat-empty">
                <span className="chat-empty-icon"><MessageCircleHeart size={30} /></span>
                <span className="eyebrow">从一个小问题开始</span>
                <h2>把复杂的育儿信息，<br />讲得简单可行</h2>
                <p>比如：“8 个月的宝宝辅食加什么”“宝宝夜里总醒怎么办”。<br />遇到紧急情况会优先提示就医。</p>
                <div className="question-templates">
                  {QUESTION_TEMPLATES.map((group) => (
                    <div className="template-group" key={group.tag}>
                      <span className="template-tag">{group.tag}</span>
                      <div className="template-items">
                        {group.items.map((item) => (
                          <button key={item} className="suggestion" onClick={() => setInput(item)}>{item}</button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((message, index) => {
                  if (message.role === "user") {
                    return <div key={index} className="user-row"><div className="user-bubble">{message.content}</div></div>;
                  }
                  const question = index > 0 && messages[index - 1].role === "user" ? messages[index - 1].content : undefined;
                  return (
                    <div key={index} className="assistant-row">
                      <AnswerCard riskLevel={message.risk_level} content={message.content} sources={message.sources} followupQuestion={message.followup_question} question={question} />
                    </div>
                  );
                })}
                {streaming && (
                  <div className="assistant-row">
                    <AnswerCard riskLevel={null} content={streamText || "正在组织回答…"} showActions={false} />
                    {streamText && <span className="typing-caret" />}
                  </div>
                )}
                {streamError && (
                  <div className="stream-error" role="alert">
                    <CircleAlert size={18} />
                    <span>{streamError}</span>
                    <button className="button secondary" onClick={() => void resend()}>
                      <RefreshCw size={15} />重新生成
                    </button>
                  </div>
                )}
              </>
            )}
            <div ref={bottomRef} />
          </div>

          <form className="composer" onSubmit={(event) => void submit(event)}>
            <div className="composer-box">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void submit();
                  }
                }}
                placeholder={`问问 ${selected.nickname} 的喂养、睡眠或日常照护…`}
                rows={1}
                aria-label="输入育儿问题"
              />
              <button type="submit" className="send-button" disabled={sending || !input.trim()} aria-label="发送问题">
                {sending ? <LoaderCircle className="spin" size={19} /> : <SendHorizonal size={19} />}
              </button>
            </div>
            <p className="composer-note">回答基于审核过的育儿指南，仅供参考，不能替代医生诊断。</p>
          </form>
        </section>
      </div>

      {dialogOpen && (
        <ChildDialog onClose={() => setDialogOpen(false)} onCreated={(child) => { setDialogOpen(false); void loadChildren(child.id); }} />
      )}
    </div>
  );
}

"use client";

import {
  BadgeCheck,
  Brain,
  Check,
  CircleAlert,
  HeartHandshake,
  LoaderCircle,
  Pencil,
  Plus,
  RefreshCw,
  ShieldCheck,
  Smartphone,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChildDialog } from "@/components/ChildDialog";
import { api } from "@/lib/api";
import { clearToken } from "@/lib/auth";
import { ageLabel } from "@/lib/format";
import type { AppError, Child, ChildFact } from "@/lib/types";

const FACT_CATEGORIES = [
  { value: "allergy", label: "过敏" },
  { value: "preference", label: "偏好" },
  { value: "milestone", label: "里程碑" },
  { value: "medical", label: "健康" },
  { value: "habit", label: "习惯" },
  { value: "note", label: "备注" },
];

export function ProfilePage() {
  const [children, setChildren] = useState<Child[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [phase, setPhase] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Child | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [facts, setFacts] = useState<ChildFact[]>([]);
  const [factsPhase, setFactsPhase] = useState<"loading" | "ready" | "error">("loading");
  const [editingFactId, setEditingFactId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<{ category: string; key: string; value: string }>({
    category: "note",
    key: "",
    value: "",
  });

  const selected = children.find((c) => c.id === selectedId) ?? children[0] ?? null;

  const loadChildren = useCallback(async (preferredId?: number) => {
    setPhase("loading");
    setError("");
    try {
      const result = await api.listChildren();
      setChildren(result.items);
      const stored = Number(window.localStorage.getItem("kids-mind-child-id"));
      const validStored = result.items.some((c) => c.id === stored) ? stored : undefined;
      setSelectedId(preferredId ?? validStored ?? result.items[0]?.id ?? null);
      setPhase("ready");
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "我的页面暂时加载失败。");
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadChildren(), 0);
    return () => window.clearTimeout(timer);
  }, [loadChildren]);

  function switchChild(id: number) {
    setSelectedId(id);
    window.localStorage.setItem("kids-mind-child-id", String(id));
  }

  async function handleAvatar(file: File) {
    if (!selected) return;
    setUploadError("");
    try {
      await api.uploadAvatar(selected.id, file);
      await loadChildren(selected.id);
    } catch (caught) {
      setUploadError((caught as AppError).userMessage ?? "头像上传失败，请稍后重试。");
    }
  }

  const loadFacts = useCallback(async (childId: number) => {
    setFactsPhase("loading");
    try {
      const result = await api.listFacts(childId);
      setFacts(result.items);
      setFactsPhase("ready");
    } catch {
      setFactsPhase("error");
    }
  }, []);

  useEffect(() => {
    if (selected?.id == null) return;
    const timer = window.setTimeout(() => void loadFacts(selected.id), 0);
    return () => window.clearTimeout(timer);
  }, [selected?.id, loadFacts]);

  function startEdit(fact: ChildFact) {
    setEditingFactId(fact.id);
    setEditDraft({ category: fact.category, key: fact.key, value: fact.value });
  }

  async function saveEdit(factId: number) {
    if (!selected) return;
    try {
      await api.updateFact(factId, editDraft);
      setEditingFactId(null);
      await loadFacts(selected.id);
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "保存失败，请稍后重试。");
    }
  }

  async function removeFact(factId: number) {
    if (!selected) return;
    if (!window.confirm("确定删除这条记忆吗？")) return;
    try {
      await api.deleteFact(factId);
      await loadFacts(selected.id);
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "删除失败，请稍后重试。");
    }
  }

  async function deleteSelected() {
    if (!selected) return;
    if (!window.confirm(`确定删除「${selected.nickname}」的档案吗？其记录、故事、问答将无法再访问。`)) return;
    try {
      await api.deleteChild(selected.id);
      await loadChildren();
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "删除失败，请稍后重试。");
    }
  }

  if (phase === "loading") {
    return <div className="page-state" role="status"><LoaderCircle className="spin" size={30} /><strong>正在读取…</strong><span>很快就好</span></div>;
  }

  if (phase === "error") {
    return <div className="page-state error-state"><CircleAlert size={30} /><strong>暂时没能连上服务</strong><span>{error}</span><button className="button secondary" onClick={() => void loadChildren()}><RefreshCw size={17} />重新连接</button></div>;
  }

  return (
    <div className="profile-page">
      <header className="topbar">
        <div><p className="kicker">我的</p><h1>孩子们</h1></div>
      </header>

      <section className="profile-section">
        <div className="profile-section-head"><span className="profile-icon"><Users size={18} /></span><div><span className="eyebrow">儿童档案</span><h2>切换孩子档案</h2></div></div>

        <div className="profile-switch">
          {children.slice(0, 3).map((child) => (
            <button key={child.id} className={child.id === selected?.id ? "profile-switch-item active" : "profile-switch-item"} onClick={() => switchChild(child.id)}>
              {/* eslint-disable-next-line @next/next/no-img-element -- 头像为家长上传的原图，无需优化 */}
              {child.avatar ? <img src={child.avatar} alt={child.nickname} className="profile-switch-avatar" /> : <span className="profile-switch-initial">{child.nickname.slice(0, 1)}</span>}
              <small>{child.nickname}</small>
            </button>
          ))}
          {children.length < 3 ? (
            <button className="profile-switch-item add" onClick={() => setDialogOpen(true)} aria-label="添加孩子">
              <span className="profile-switch-initial"><Plus size={20} /></span>
              <small>添加</small>
            </button>
          ) : null}
        </div>

        {selected ? (
          <div className="profile-kid-card">
            <button className="profile-avatar-wrap" onClick={() => fileRef.current?.click()} aria-label="上传头像">
              {/* eslint-disable-next-line @next/next/no-img-element -- 头像为家长上传的原图，无需优化 */}
              {selected.avatar ? <img src={selected.avatar} alt={selected.nickname} className="profile-avatar" /> : <span className="profile-avatar-initial">{selected.nickname.slice(0, 1)}</span>}
              <span className="profile-avatar-edit">更换头像</span>
            </button>
            <div className="profile-kid-info">
              <h2>{selected.nickname}</h2>
              <p>{ageLabel(selected.birth_date)}{selected.gender ? ` · ${selected.gender}` : ""}{selected.feeding_method ? ` · ${selected.feeding_method}` : ""}</p>
              {selected.allergy_history ? <p className="profile-kid-allergy">过敏史：{selected.allergy_history}</p> : null}
            </div>
            <div className="profile-kid-actions">
              <button className="icon-button" onClick={() => setEditing(selected)} aria-label="编辑档案"><Pencil size={16} /></button>
              <button className="icon-button danger" onClick={() => void deleteSelected()} aria-label="删除档案"><Trash2 size={16} /></button>
            </div>
          </div>
        ) : (
          <button className="button secondary" onClick={() => setDialogOpen(true)}><Plus size={16} />添加第一个孩子</button>
        )}
        <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) void handleAvatar(f); e.target.value = ""; }} />
        {uploadError && <p className="form-error" role="alert" style={{ marginTop: 10 }}>{uploadError}</p>}
      </section>

      <section className="profile-section">
        <div className="profile-section-head"><span className="profile-icon"><Brain size={18} /></span><div><span className="eyebrow">育儿管家记忆</span><h2>AI 帮你记住的</h2></div></div>
        {factsPhase === "loading" ? (
          <p className="profile-muted">正在读取记忆…</p>
        ) : factsPhase === "error" ? (
          <p className="profile-muted">记忆暂时读不出来，请稍后刷新重试。</p>
        ) : facts.length === 0 ? (
          <div className="fact-empty">
            <p>还没有记住任何关于孩子的事实。</p>
            <small>去首页说一句「宝宝对鸡蛋过敏，帮我记一下」，AI 就会自动记在这里。</small>
          </div>
        ) : (
          <ul className="fact-list">
            {facts.map((fact) => (
              <li key={fact.id} className="fact-item">
                {editingFactId === fact.id ? (
                  <div className="fact-edit">
                    <select
                      value={editDraft.category}
                      onChange={(e) => setEditDraft({ ...editDraft, category: e.target.value })}
                      aria-label="记忆类别"
                    >
                      {FACT_CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                    </select>
                    <input
                      value={editDraft.key}
                      onChange={(e) => setEditDraft({ ...editDraft, key: e.target.value })}
                      placeholder="名称，如 鸡蛋"
                      maxLength={100}
                    />
                    <input
                      value={editDraft.value}
                      onChange={(e) => setEditDraft({ ...editDraft, value: e.target.value })}
                      placeholder="内容，如 过敏"
                      maxLength={500}
                    />
                    <div className="fact-edit-actions">
                      <button className="icon-button" onClick={() => void saveEdit(fact.id)} aria-label="保存记忆"><Check size={16} /></button>
                      <button className="icon-button" onClick={() => setEditingFactId(null)} aria-label="取消"><X size={16} /></button>
                    </div>
                  </div>
                ) : (
                  <div className="fact-row">
                    <span className="fact-badge">{fact.category_label}</span>
                    <span className="fact-text"><strong>{fact.key}</strong>：{fact.value}{fact.source === "ai_extract" ? <span className="fact-source">AI 提取</span> : null}</span>
                    <span className="fact-actions">
                      <button className="icon-button" onClick={() => startEdit(fact)} aria-label="编辑记忆"><Pencil size={14} /></button>
                      <button className="icon-button danger" onClick={() => void removeFact(fact.id)} aria-label="删除记忆"><Trash2 size={14} /></button>
                    </span>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
        {facts.some((f) => f.source === "ai_extract") ? (
          <p className="fact-note">带「AI 提取」标记的记忆由 AI 从对话中自动记录，可能不准确，可随时修改或删除。</p>
        ) : null}
      </section>

      <section className="profile-section">
        <div className="profile-section-head"><span className="profile-icon"><ShieldCheck size={18} /></span><div><span className="eyebrow">隐私与数据</span><h2>我们怎么对待你的数据</h2></div></div>
        <ul className="profile-facts">
          <li><ShieldCheck size={16} /><span><strong>数据留在国内</strong><small>儿童档案、成长记录、故事都存在你自己的服务里，不出境</small></span></li>
          <li><HeartHandshake size={16} /><span><strong>敏感信息不训练</strong><small>儿童照片、音频、健康记录默认不公开、不用于训练</small></span></li>
          <li><Smartphone size={16} /><span><strong>提醒只在手机本地触发</strong><small>闹钟提醒由你手机系统本地触发，内容不上传第三方</small></span></li>
        </ul>
      </section>

      <section className="profile-section">
        <div className="profile-section-head"><span className="profile-icon"><BadgeCheck size={18} /></span><div><span className="eyebrow">关于</span><h2>版本与说明</h2></div></div>
        <ul className="profile-facts">
          <li><BadgeCheck size={16} /><span><strong>知芽 v1.0（内部试用版）</strong><small>育儿问答 · 成长记录 · 提醒 · 数字绘本</small></span></li>
        </ul>
        <div className="profile-disclaimer"><CircleAlert size={15} /><span>知芽提供育儿信息参考，不能替代医生诊断。如遇窒息、意识丧失、抽搐等危急情况，请立即拨打 120。</span></div>
      </section>

      <button className="logout-button" onClick={() => { clearToken(); window.location.replace("/"); }}>退出登录</button>

      {dialogOpen && <ChildDialog onClose={() => setDialogOpen(false)} onCreated={(child) => { setDialogOpen(false); void loadChildren(child.id); }} />}
      {editing && <ChildDialog child={editing} onClose={() => setEditing(null)} onUpdated={() => { setEditing(null); void loadChildren(); }} />}
    </div>
  );
}

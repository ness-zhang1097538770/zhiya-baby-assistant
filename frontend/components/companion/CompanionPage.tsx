"use client";

import {
  Activity,
  ChevronDown,
  CircleAlert,
  HeartHandshake,
  LoaderCircle,
  Moon,
  Plus,
  RefreshCw,
  Smile,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ChildDialog } from "@/components/ChildDialog";
import { api } from "@/lib/api";
import { ageLabel } from "@/lib/format";
import type { AppError, Child, CompanionScript, EmotionResult } from "@/lib/types";

const MODES = [
  { value: "separation", label: "分离焦虑安抚", desc: "分开时不安、哭闹", icon: HeartHandshake },
  { value: "emotion", label: "情绪调节", desc: "烦躁、发脾气、受挫", icon: Smile },
  { value: "sleep", label: "睡前陪伴", desc: "放松身体、准备入睡", icon: Moon },
];

export function CompanionPage() {
  const [children, setChildren] = useState<Child[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [phase, setPhase] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [mode, setMode] = useState("separation");
  const [text, setText] = useState("");
  const [emotion, setEmotion] = useState<EmotionResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [script, setScript] = useState<CompanionScript | null>(null);
  const [vibrating, setVibrating] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);

  const selected = children.find((c) => c.id === selectedId) ?? children[0] ?? null;

  const loadChildren = useCallback(async () => {
    setPhase("loading");
    setError("");
    try {
      const r = await api.listChildren();
      setChildren(r.items);
      const stored = Number(window.localStorage.getItem("kids-mind-child-id"));
      setSelectedId(r.items.some((c) => c.id === stored) ? stored : r.items[0]?.id ?? null);
      setPhase("ready");
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "陪伴页暂时加载失败。");
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadChildren(), 0);
    return () => window.clearTimeout(timer);
  }, [loadChildren]);

  async function analyze() {
    if (!text.trim()) return;
    setAnalyzing(true);
    setEmotion(null);
    setError("");
    try {
      const r = await api.analyzeEmotion(text.trim());
      setEmotion(r);
      setMode(r.mode);
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "识别失败，请稍后重试。");
    } finally {
      setAnalyzing(false);
    }
  }

  async function generate() {
    setGenerating(true);
    setScript(null);
    setError("");
    try {
      const r = await api.generateCompanion({
        mode,
        child_nickname: selected?.nickname,
        situation: text.trim() || undefined,
        gender: selected?.gender ?? "女孩",
      });
      setScript(r);
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "生成失败，请稍后重试。");
    } finally {
      setGenerating(false);
    }
  }

  function vibrate() {
    if (!script) return;
    if (!("vibrate" in navigator)) {
      setError("当前设备不支持震动反馈。");
      return;
    }
    setVibrating(true);
    const { in: bIn, out: bOut } = script.breathing;
    const pattern = [bIn * 1000, bOut * 1000];
    const full = Array.from({ length: 10 }, () => pattern).flat();
    navigator.vibrate(full);
    window.setTimeout(() => setVibrating(false), (bIn + bOut) * 10 * 1000);
  }

  if (phase === "loading") {
    return <div className="page-state" role="status"><LoaderCircle className="spin" size={30} /><strong>正在准备陪伴…</strong><span>稍等</span></div>;
  }

  if (phase === "error") {
    return <div className="page-state error-state"><CircleAlert size={30} /><strong>暂时没能连上服务</strong><span>{error}</span><button className="button secondary" onClick={() => void loadChildren()}><RefreshCw size={17} />重新连接</button></div>;
  }

  return (
    <div className="companion-page">
      <header className="topbar">
        <div><p className="kicker">智慧陪伴</p><h1>陪 <em>{selected ? selected.nickname : "宝贝"}</em> 度过这一刻</h1></div>
        <div className="child-picker-wrap">
          <select className="child-picker" value={selected?.id ?? ""} onChange={(e) => { setSelectedId(Number(e.target.value)); window.localStorage.setItem("kids-mind-child-id", String(e.target.value)); }} aria-label="切换孩子">
            {children.map((child) => <option key={child.id} value={child.id}>{child.nickname} · {ageLabel(child.birth_date)}</option>)}
          </select>
          <ChevronDown size={16} aria-hidden="true" />
          <button className="add-child" onClick={() => setDialogOpen(true)} aria-label="添加孩子"><Plus size={18} /></button>
        </div>
      </header>

      <section className="companion-emotion">
        <div className="companion-card-head"><span className="eyebrow">情绪识别</span><h2>先说说孩子现在怎么样</h2></div>
        <div className="emotion-input-row">
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} placeholder="例如：我要出门上班，宝宝抱着我大哭不撒手…" aria-label="描述孩子状态" />
          <button className="button primary" onClick={() => void analyze()} disabled={analyzing || !text.trim()}>{analyzing ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}{analyzing ? "识别中…" : "识别情绪"}</button>
        </div>
        {emotion && (
          <div className="emotion-result">
            <span className="emotion-tag">{emotion.emotion}</span>
            <span>建议：<strong>{MODES.find((m) => m.value === emotion.mode)?.label ?? emotion.mode}</strong> · {emotion.suggestion}</span>
          </div>
        )}
      </section>

      <section className="companion-modes">
        <div className="companion-card-head"><span className="eyebrow">陪伴模式</span><h2>选一种陪伴方式</h2></div>
        <div className="mode-grid">
          {MODES.map((m) => {
            const Icon = m.icon;
            return (
              <button key={m.value} className={mode === m.value ? "mode-card active" : "mode-card"} onClick={() => setMode(m.value)}>
                <span className="mode-icon"><Icon size={22} /></span>
                <strong>{m.label}</strong>
                <small>{m.desc}</small>
              </button>
            );
          })}
        </div>
      </section>

      <button className="button primary large companion-generate" onClick={() => void generate()} disabled={generating}>
        {generating ? <LoaderCircle className="spin" size={19} /> : <HeartHandshake size={19} />}{generating ? "正在生成陪伴内容…" : "开始陪伴"}
      </button>

      {error && <p className="form-error" role="alert">{error}</p>}

      {script && (
        <section className="companion-result">
          <div className="companion-card-head"><span className="eyebrow">陪伴内容</span><h2>{script.title}</h2></div>
          <ol className="companion-segments">
            {script.segments.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
          <div className="companion-controls">
            <audio controls src={script.audio_url} className="companion-audio" />
            <button className="button secondary" onClick={vibrate} disabled={vibrating}>
              <Activity size={16} />{vibrating ? "震动中…" : `呼吸节奏震动（吸 ${script.breathing.in} 秒 · 呼 ${script.breathing.out} 秒）`}
            </button>
          </div>
          <p className="companion-tip">语音朗读会逐句念出上面的内容；震动可引导孩子跟着呼吸节奏放松（手机需支持震动）。</p>
        </section>
      )}

      {dialogOpen && <ChildDialog onClose={() => setDialogOpen(false)} onCreated={(child) => { setDialogOpen(false); void loadChildren(); setSelectedId(child.id); }} />}
    </div>
  );
}

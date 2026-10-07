"use client";

import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CircleAlert,
  LoaderCircle,
  Play,
  RefreshCw,
  Sparkles,
  Square,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { isStoryRunning, storyStatusLabel } from "@/lib/format";
import type { AppError, Story, StoryCharacter, StoryOutlinePage } from "@/lib/types";

const RUNNING_HINTS: Record<string, string> = {
  character_generating: "正在设计绘本角色…",
  outline_generating: "正在根据主题构思故事大纲…",
  content_generating: "正在把每一页写成正文…",
  assets_generating: "正在为每一页画插画、配朗读（约需几分钟）…",
};

export function StoryDetailPage({ storyId }: { storyId: number }) {
  const [story, setStory] = useState<Story | null>(null);
  const [phase, setPhase] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [stopping, setStopping] = useState(false);

  const load = useCallback(async () => {
    try {
      const result = await api.getStory(storyId);
      setStory(result);
      setPhase("ready");
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "故事加载失败。");
      setPhase("error");
    }
  }, [storyId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    if (!story || !isStoryRunning(story.status)) return;
    const timer = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(timer);
  }, [story, load]);

  async function runAction(fn: () => Promise<Story>) {
    setBusy(true);
    setActionError("");
    try {
      const result = await fn();
      setStory(result);
      if (isStoryRunning(result.status)) void load();
    } catch (caught) {
      setActionError((caught as AppError).userMessage ?? "操作失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }

  async function cancelGeneration() {
    if (!story) return;
    setStopping(true);
    setActionError("");
    try {
      const result = await api.cancelStory(story.id);
      setStory(result);
    } catch (caught) {
      setActionError((caught as AppError).userMessage ?? "停止失败，请稍后重试。");
      setStopping(false);
    }
  }

  if (phase === "loading") {
    return <div className="page-state" role="status"><LoaderCircle className="spin" size={30} /><strong>正在翻开这本书…</strong><span>稍等一下</span></div>;
  }

  if (phase === "error" || !story) {
    return (
      <div className="page-state error-state"><CircleAlert size={30} /><strong>没能打开这个故事</strong><span>{error}</span><button className="button secondary" onClick={() => void load()}><RefreshCw size={17} />重试</button><Link href="/stories" className="button ghost"><ArrowLeft size={16} />回到书架</Link></div>
    );
  }

  return (
    <div className="story-detail">
      <header className="story-detail-top">
        <Link href="/stories" className="text-link"><ArrowLeft size={16} />回到书架</Link>
        <h1>{story.title || story.theme}</h1>
        <span className={`story-status ${story.status}`}>{storyStatusLabel(story.status)}</span>
      </header>

      {actionError && <p className="form-error" role="alert">{actionError}</p>}

      {isStoryRunning(story.status) ? (
        <RunningView status={story.status} onCancel={() => void cancelGeneration()} busy={stopping} stopping={stopping} />
      ) : story.status === "character_ready" ? (
        <CharacterView story={story} busy={busy} onConfirm={(character) => runAction(() => api.confirmStoryCharacter(story.id, character))} onRegenerate={(payload) => runAction(() => api.regenerateCharacterImage(story.id, payload))} />
      ) : story.status === "outline_ready" ? (
        <OutlineView story={story} busy={busy} onConfirm={(outline) => runAction(() => api.confirmStory(story.id, outline))} onRegenerate={() => runAction(() => api.regenerateOutline(story.id))} />
      ) : story.status === "content_ready" ? (
        <ContentView story={story} busy={busy} onGenerate={() => runAction(() => api.generateStoryAssets(story.id))} />
      ) : story.status === "ready" ? (
        <Reader story={story} />
      ) : story.status === "failed" ? (
        <div className="story-failed"><CircleAlert size={30} /><strong>生成失败</strong><p>{story.error || "请稍后重试，或回书架重新创作。"}</p><Link href="/stories" className="button secondary"><ArrowLeft size={16} />回到书架</Link></div>
      ) : story.status === "cancelled" ? (
        <div className="story-failed"><Square size={30} /><strong>已停止生成</strong><p>这本故事已取消，可以回书架重新创作。</p><Link href="/stories" className="button secondary"><ArrowLeft size={16} />回到书架</Link></div>
      ) : null}
    </div>
  );
}

function RunningView({ status, onCancel, busy, stopping }: { status: string; onCancel: () => void; busy: boolean; stopping: boolean }) {
  return (
    <div className="story-running">
      <span className="story-running-orb"><LoaderCircle className="spin" size={30} /></span>
      <strong>{stopping ? "正在停止…" : storyStatusLabel(status)}</strong>
      <p>{stopping ? "已收到停止请求，当前这一小步做完就会停" : RUNNING_HINTS[status] ?? "正在生成…"}</p>
      <button className="button secondary" onClick={onCancel} disabled={busy}><Square size={15} />{stopping ? "正在停止…" : "停止生成"}</button>
    </div>
  );
}

function CharacterView({ story, busy, onConfirm, onRegenerate }: { story: Story; busy: boolean; onConfirm: (character: StoryCharacter) => void; onRegenerate: (payload: { look: string; art_style: string }) => void }) {
  const c = story.character;
  const [heroName, setHeroName] = useState(c?.hero?.name || story.character_name);
  const [heroLook, setHeroLook] = useState(c?.hero?.look || "");
  const [heroPersonality, setHeroPersonality] = useState(c?.hero?.personality || "");
  const [companions, setCompanions] = useState(c?.companions ?? []);
  const [artStyle, setArtStyle] = useState(c?.art_style || "");

  function updateCompanion(index: number, field: "name" | "look" | "personality", value: string) {
    setCompanions((prev) => prev.map((cp, i) => (i === index ? { ...cp, [field]: value } : cp)));
  }

  function regenerate() {
    onRegenerate({ look: heroLook.trim(), art_style: artStyle.trim() });
  }

  function submit() {
    onConfirm({
      hero: { name: heroName.trim(), look: heroLook.trim(), personality: heroPersonality.trim() },
      companions: companions.filter((cp) => cp.name.trim()),
      art_style: artStyle.trim(),
    });
  }

  return (
    <div className="outline-view">
      <div className="outline-head"><span className="eyebrow">第一步 · 确认绘本角色</span><h2>角色满意吗？</h2><p>AI 已设计好主角和配角，可改名字、外貌、性格；满意后点「确认并生成故事大纲」。</p></div>
      <div className="character-image-preview">
        {story.character_image && (
          /* eslint-disable-next-line @next/next/no-img-element -- 后端生成的角色形象图，无需优化 */
          <img src={story.character_image} alt="根据孩子照片生成的角色形象" />
        )}
        <p>{story.character_image ? "这是根据孩子照片生成的角色形象，会作为绘本主角参考；不满意可重新生成。" : "还没有角色形象图，点下方按钮生成一张。"}</p>
        <button className="button secondary" type="button" disabled={busy} onClick={regenerate}>
          <RefreshCw size={15} /> {busy ? "正在生成…" : story.character_image ? "重新生成角色形象" : "生成角色形象"}
        </button>
      </div>
      <div className="character-hero">
        <label className="outline-title"><span>主角名字</span><input value={heroName} onChange={(e) => setHeroName(e.target.value)} maxLength={20} /></label>
        <label className="outline-title"><span>主角外貌</span><input value={heroLook} onChange={(e) => setHeroLook(e.target.value)} maxLength={100} placeholder="如：戴着黄色小帽，圆脸，穿蓝色背带裤" /></label>
        <label className="outline-title"><span>主角性格</span><input value={heroPersonality} onChange={(e) => setHeroPersonality(e.target.value)} maxLength={50} placeholder="如：勇敢、好奇" /></label>
      </div>
      {companions.map((cp, index) => (
        <div className="character-companion" key={index}>
          <span className="eyebrow">配角 {index + 1}</span>
          <label className="outline-title"><span>配角名字</span><input value={cp.name} onChange={(e) => updateCompanion(index, "name", e.target.value)} maxLength={20} /></label>
          <label className="outline-title"><span>配角外貌</span><input value={cp.look} onChange={(e) => updateCompanion(index, "look", e.target.value)} maxLength={100} /></label>
          <label className="outline-title"><span>配角性格</span><input value={cp.personality} onChange={(e) => updateCompanion(index, "personality", e.target.value)} maxLength={50} /></label>
        </div>
      ))}
      <label className="outline-title"><span>整体画风</span><input value={artStyle} onChange={(e) => setArtStyle(e.target.value)} maxLength={100} placeholder="如：温暖水彩童趣风，色彩柔和" /></label>
      <button className="button primary large" disabled={busy} onClick={submit}>{busy ? "正在提交…" : "确认并生成故事大纲"}</button>
    </div>
  );
}

function OutlineView({ story, busy, onConfirm, onRegenerate }: { story: Story; busy: boolean; onConfirm: (outline: { title: string; pages: StoryOutlinePage[] }) => void; onRegenerate: () => void }) {
  const [title, setTitle] = useState(story.outline?.title ?? "");
  const [pages, setPages] = useState<StoryOutlinePage[]>(story.outline?.pages ?? []);

  function updatePage(index: number, outline: string) {
    setPages((prev) => prev.map((p, i) => (i === index ? { ...p, outline } : p)));
  }

  return (
    <div className="outline-view">
      <div className="outline-head"><span className="eyebrow">第二步 · 确认故事大纲</span><h2>大纲满意吗？</h2><p>可以改标题和每一页的内容，满意后点「确认并生成正文」。</p></div>
      <label className="outline-title"><span>故事标题</span><input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={100} /></label>
      <div className="outline-pages">
        {pages.map((page, index) => (
          <label key={page.page_no} className="outline-page"><span>第 {page.page_no} 页</span><textarea value={page.outline} rows={2} onChange={(e) => updatePage(index, e.target.value)} /></label>
        ))}
      </div>
      <div className="outline-actions">
        <button className="button primary large" disabled={busy} onClick={() => onConfirm({ title: title.trim(), pages })}>{busy ? "正在提交…" : "确认并生成正文"}</button>
        <button className="button secondary" type="button" disabled={busy} onClick={onRegenerate}><RefreshCw size={15} />重新生成大纲</button>
      </div>
    </div>
  );
}

function ContentView({ story, busy, onGenerate }: { story: Story; busy: boolean; onGenerate: () => void }) {
  const pages = story.pages?.pages ?? [];
  return (
    <div className="outline-view">
      <div className="outline-head"><span className="eyebrow">第三步 · 生成插画与朗读</span><h2>正文写好了</h2><p>共 {pages.length} 页。确认没问题，就为它配上插画和朗读（约几分钟）。</p></div>
      <div className="content-pages">
        {pages.map((page) => (
          <div className="content-page" key={page.page_no}>
            <span className="content-page-no">第 {page.page_no} 页</span>
            <p>{page.text}</p>
          </div>
        ))}
      </div>
      <button className="button primary large" disabled={busy} onClick={onGenerate}><Sparkles size={17} />{busy ? "正在开始…" : "生成插画和朗读"}</button>
    </div>
  );
}

function Reader({ story }: { story: Story }) {
  const pages = story.pages?.pages ?? [];
  const [current, setCurrent] = useState(0);
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);
  const startedPageRef = useRef(0);

  const page = pages[current];
  const imageUrl = page ? story.images?.find((i) => i.page_no === page.page_no)?.url : undefined;
  const audioUrl = page ? story.audio?.find((a) => a.page_no === page.page_no)?.url : undefined;

  // 自动翻页后播下一页（首次播放由「连续朗读」按钮直接触发）
  useEffect(() => {
    if (!playing) return;
    if (startedPageRef.current === current) return;
    startedPageRef.current = current;
    const audio = audioRef.current;
    if (audio) void audio.play().catch(() => setPlaying(false));
  }, [playing, current]);

  if (!page) {
    return <div className="story-failed"><BookOpen size={30} /><strong>这本书还没有正文</strong><Link href="/stories" className="button secondary">回到书架</Link></div>;
  }

  function startContinuous() {
    setPlaying(true);
    startedPageRef.current = current;
    const audio = audioRef.current;
    if (audio) void audio.play().catch(() => setPlaying(false));
  }

  function stop() {
    setPlaying(false);
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
  }

  function go(delta: number) {
    const next = Math.min(Math.max(current + delta, 0), pages.length - 1);
    if (next === current) return;
    // 暂停当前页音频但不中断连续朗读：若正在朗读，翻页后 effect 会自动续播新的一页
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    setCurrent(next);
  }

  function handleEnded() {
    if (current < pages.length - 1) {
      setCurrent((prev) => prev + 1); // 自动翻页，effect 会播下一页
    } else {
      setPlaying(false); // 最后一页读完，停止
    }
  }

  return (
    <div className="reader">
      <div className="reader-stage">
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- 绘本插画为后端生成的原尺寸静态图，无需优化
          <img src={imageUrl} alt={`第 ${page.page_no} 页插画`} className="reader-img" />
        ) : (
          <div className="reader-img placeholder"><BookOpen size={44} /></div>
        )}
        <div className="reader-text">
          <span className="reader-page-no">{page.page_no} / {pages.length}{playing ? " · 朗读中" : ""}</span>
          <p>{page.text}</p>
        </div>
      </div>
      <div className="reader-controls">
        <button className="icon-button" onClick={() => go(-1)} disabled={current === 0} aria-label="上一页"><ArrowLeft size={18} /></button>
        {audioUrl ? (
          playing ? (
            <button className="reader-stop" onClick={stop} aria-label="停止朗读"><Square size={18} /> 停止</button>
          ) : (
            <button className="reader-play" onClick={startContinuous} aria-label="连续朗读"><Play size={18} /> 连续朗读</button>
          )
        ) : (
          <span className="reader-no-audio">暂无朗读</span>
        )}
        <button className="icon-button" onClick={() => go(1)} disabled={current === pages.length - 1} aria-label="下一页"><ArrowRight size={18} /></button>
        <audio ref={audioRef} src={audioUrl} onEnded={handleEnded} />
      </div>
    </div>
  );
}

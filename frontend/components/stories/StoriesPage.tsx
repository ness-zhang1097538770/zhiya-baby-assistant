"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  BookOpen,
  ChevronDown,
  CircleAlert,
  LoaderCircle,
  Plus,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ChildDialog } from "@/components/ChildDialog";
import { api } from "@/lib/api";
import { ageLabel, storyCover, storyStatusLabel } from "@/lib/format";
import type { AppError, Child, Story } from "@/lib/types";
import { StoryCreateDialog } from "./StoryCreateDialog";

export function StoriesPage() {
  const router = useRouter();
  const [children, setChildren] = useState<Child[]>([]);
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null);
  const [stories, setStories] = useState<Story[]>([]);
  const [phase, setPhase] = useState<"loading" | "no-child" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [childDialogOpen, setChildDialogOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [initialTheme, setInitialTheme] = useState<string | undefined>(undefined);
  const [quota, setQuota] = useState<number | null>(null);

  const selected = children.find((child) => child.id === selectedChildId) ?? null;

  const loadQuota = useCallback(async () => {
    try {
      const e = await api.getEntitlements();
      setQuota(e.story_books_available);
    } catch {
      setQuota(null);
    }
  }, []);

  const loadStories = useCallback(async (childId: number) => {
    const result = await api.listStories(childId);
    setStories(result.items);
    setPhase("ready");
  }, []);

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
          setStories([]);
          setPhase("no-child");
          return;
        }
        setSelectedChildId(targetId);
        window.localStorage.setItem("kids-mind-child-id", String(targetId));
        await loadStories(targetId);
      } catch (caught) {
        setError((caught as AppError).userMessage ?? "书架暂时加载失败。");
        setPhase("error");
      }
    },
    [loadStories],
  );

  useEffect(() => {
    const theme = new URLSearchParams(window.location.search).get("theme");
    if (theme) {
      window.history.replaceState({}, "", window.location.pathname);
      window.setTimeout(() => {
        setInitialTheme(theme);
        setCreateOpen(true);
      }, 0);
    }
    const timer = window.setTimeout(() => void loadChildren(), 0);
    return () => window.clearTimeout(timer);
  }, [loadChildren]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadQuota(), 0);
    return () => window.clearTimeout(timer);
  }, [loadQuota]);

  function changeChild(id: number) {
    window.localStorage.setItem("kids-mind-child-id", String(id));
    setSelectedChildId(id);
    void loadStories(id);
  }

  if (phase === "loading") {
    return <div className="page-state" role="status"><LoaderCircle className="spin" size={30} /><strong>正在整理书架…</strong><span>孩子的小故事很快就好</span></div>;
  }

  if (phase === "error") {
    return <div className="page-state error-state"><CircleAlert size={30} /><strong>暂时没能连上服务</strong><span>{error}</span><button className="button secondary" onClick={() => void loadChildren()}><RefreshCw size={17} />重新连接</button></div>;
  }

  if (!selected) {
    return (
      <div className="empty-home">
        <div className="onboarding-visual">
          <Image src="/illustrations/empty-state.jpg" alt="温暖水彩插画：小动物与嫩芽" width={420} height={315} priority />
        </div>
        <span className="eyebrow">故事工坊</span>
        <h1>先建立档案，<br />故事才有小主角</h1>
        <p>把孩子变成故事主角，生成可读、可听的专属绘本。</p>
        <button className="button primary large" onClick={() => setChildDialogOpen(true)}><Plus size={19} />建立成长档案</button>
        {childDialogOpen && <ChildDialog onClose={() => setChildDialogOpen(false)} onCreated={(child) => { setChildDialogOpen(false); void loadChildren(child.id); }} />}
      </div>
    );
  }

  return (
    <div className="stories-page">
      <header className="topbar">
        <div><p className="kicker">故事工坊</p><h1><em>{selected.nickname}</em> 的小小书架</h1></div>
        <div className="child-picker-wrap">
          <select className="child-picker" value={selected.id} onChange={(e) => changeChild(Number(e.target.value))} aria-label="切换孩子">
            {children.map((child) => <option key={child.id} value={child.id}>{child.nickname} · {ageLabel(child.birth_date)}</option>)}
          </select>
          <ChevronDown size={16} aria-hidden="true" />
          <button className="add-child" onClick={() => setChildDialogOpen(true)} aria-label="添加孩子"><Plus size={18} /></button>
        </div>
      </header>

      <div className="stories-toolbar">
        <p className="reminder-summary">{stories.length ? `共 ${stories.length} 本故事` : "把孩子的名字写进故事里，今晚就能读"}{quota != null ? ` · 本月剩余 ${quota} 本` : ""}</p>
        <button className="button primary" onClick={() => setCreateOpen(true)}><Sparkles size={17} />创作故事</button>
      </div>

      {stories.length === 0 ? (
        <div className="soft-empty tall">
          <BookOpen size={30} />
          <span><strong>书架还是空的</strong><small>创作第一本：选个主题，AI 会写大纲、正文、配插画和朗读</small></span>
          <button className="button secondary" onClick={() => setCreateOpen(true)}><Plus size={16} />创作故事</button>
        </div>
      ) : (
        <div className="story-grid">
          {stories.map((story) => {
            const cover = storyCover(story.images);
            return (
              <Link href={`/stories/${story.id}`} className="story-card" key={story.id}>
                <div className="story-card-cover" style={cover ? { backgroundImage: `linear-gradient(180deg, transparent 30%, rgba(16,45,41,.55)), url(${cover})` } : undefined}>
                  {!cover && <><span className="story-card-moon" /><span className="story-card-hill" /></>}
                  <span className="story-card-icon"><BookOpen size={15} /></span>
                </div>
                <div className="story-card-body">
                  <span className={`story-status ${story.status}`}>{storyStatusLabel(story.status)}</span>
                  <strong>{story.title || story.theme}</strong>
                  <small>{story.character_name} · {story.theme}</small>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {childDialogOpen && <ChildDialog onClose={() => setChildDialogOpen(false)} onCreated={(child) => { setChildDialogOpen(false); void loadChildren(child.id); }} />}
      {createOpen && (
        <StoryCreateDialog
          childId={selected.id}
          initialTheme={initialTheme}
          onClose={() => setCreateOpen(false)}
          onCreated={(story) => { setCreateOpen(false); void loadStories(selected.id); void loadQuota(); router.push(`/stories/${story.id}`); }}
        />
      )}
    </div>
  );
}

"use client";

import Link from "next/link";
import Image from "next/image";
import { ArrowRight, Bell, BookOpen, CalendarDays, ChevronDown, CircleAlert, HeartPulse, LoaderCircle, Plus, RefreshCw, Sprout } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ageLabel, eventLabel, formatClock, storyCover } from "@/lib/format";
import type { AppError, Child, GrowthEvent, Reminder, Story } from "@/lib/types";
import { AdSlot } from "./AdSlot";
import { ChildDialog } from "./ChildDialog";
import { IntentBar } from "./IntentBar";

type DashboardData = { reminders: Reminder[]; events: GrowthEvent[]; stories: Story[] };

const emptyData: DashboardData = { reminders: [], events: [], stories: [] };

function greeting() {
  const hour = new Date().getHours();
  if (hour < 11) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

function ageBucket(birthDate: string): string {
  const parts = birthDate.split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return "1-3";
  const [y, m, d] = parts;
  const now = new Date();
  let months = (now.getFullYear() - y) * 12 + (now.getMonth() + 1 - m);
  if (now.getDate() < d) months -= 1;
  return months < 12 ? "0-1" : "1-3";
}

export function HomeDashboard() {
  const [children, setChildren] = useState<Child[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [data, setData] = useState<DashboardData>(emptyData);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [isMember, setIsMember] = useState(false);

  const selected = children.find((child) => child.id === selectedId) ?? null;

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void api.getEntitlements().then((e) => setIsMember(e.plan !== "free")).catch(() => setIsMember(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const loadDashboard = useCallback(async (preferredId?: number) => {
    setState("loading");
    setError("");
    try {
      const childResult = await api.listChildren();
      setChildren(childResult.items);
      const stored = Number(window.localStorage.getItem("kids-mind-child-id"));
      const validStored = childResult.items.some((child) => child.id === stored) ? stored : undefined;
      const targetId = preferredId ?? validStored ?? childResult.items[0]?.id;
      setSelectedId(targetId ?? null);
      if (!targetId) {
        setData(emptyData);
        setState("ready");
        return;
      }
      window.localStorage.setItem("kids-mind-child-id", String(targetId));
      const [reminders, events, stories] = await Promise.all([
        api.listUpcomingReminders(targetId),
        api.listEvents(targetId),
        api.listStories(targetId),
      ]);
      setData({ reminders: reminders.items, events: events.items, stories: stories.items });
      setState("ready");
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "首页数据暂时加载失败。");
      setState("error");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadDashboard(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadDashboard]);

  async function changeChild(id: number) {
    window.localStorage.setItem("kids-mind-child-id", String(id));
    await loadDashboard(id);
  }

  if (state === "loading") {
    return <div className="page-state" role="status"><LoaderCircle className="spin" size={30} /><strong>正在整理今天的育儿小事…</strong><span>孩子档案和提醒很快就好</span></div>;
  }

  if (state === "error") {
    return <div className="page-state error-state"><CircleAlert size={30} /><strong>暂时没能连上服务</strong><span>{error}</span><button className="button secondary" onClick={() => void loadDashboard()}><RefreshCw size={17} />重新连接</button></div>;
  }

  if (!selected) {
    return (
      <div className="empty-home">
        <div className="onboarding-visual">
          <Image src="/illustrations/onboarding.jpg" alt="明亮的育婴室里，亲子温柔互动" width={420} height={315} priority />
        </div>
        <span className="eyebrow">欢迎来到知芽</span>
        <h1>从一份小档案开始，<br />陪孩子慢慢长大</h1>
        <p>建档后，育儿建议会自动结合孩子的月龄和喂养情况。</p>
        <button className="button primary large" onClick={() => setDialogOpen(true)}><Plus size={19} />建立第一份成长档案</button>
        {dialogOpen && <ChildDialog onClose={() => setDialogOpen(false)} onCreated={(child) => { setDialogOpen(false); void loadDashboard(child.id); }} />}
      </div>
    );
  }

  const latestEvent = data.events[0];
  const latestStory = data.stories[0];
  const cover = latestStory ? storyCover(latestStory.images) : null;

  return (
    <div className="dashboard">
      <header className="topbar">
        <div><p className="kicker">{greeting()}，家长</p><h1>今天也一起读懂 <em>{selected.nickname}</em> 的成长</h1></div>
        <div className="child-picker-wrap">
          <select className="child-picker" value={selected.id} onChange={(event) => void changeChild(Number(event.target.value))} aria-label="切换孩子">
            {children.map((child) => <option key={child.id} value={child.id}>{child.nickname} · {ageLabel(child.birth_date)}</option>)}
          </select>
          <ChevronDown size={16} aria-hidden="true" />
          <button className="add-child" onClick={() => setDialogOpen(true)} aria-label="添加孩子"><Plus size={18} /></button>
        </div>
      </header>

      <IntentBar childId={selected.id} />

      <section className="hero-grid">
        <article className="care-card">
          <div className="soft-shape shape-a" /><div className="soft-shape shape-b" />
          <span className="care-icon"><HeartPulse size={22} /></span>
          <div className="care-copy"><span className="eyebrow">遇到育儿难题？</span><h2>问一句，得到适合<br /><strong>{ageLabel(selected.birth_date)}</strong> 宝宝的可执行建议</h2><p>基于审核过的育儿指南，遇到紧急情况会优先提醒就医。</p></div>
          <Link href="/ask" className="button light">去问育儿助手 <ArrowRight size={18} /></Link>
        </article>

        <article className="today-card">
          <div className="section-heading"><div><span className="eyebrow">今日照护</span><h2>今天别忘了</h2></div><span className="count-badge">{data.reminders.length}</span></div>
          {data.reminders.length ? (
            <div className="reminder-list">
              {data.reminders.slice(0, 3).map((item, index) => (
                <div className="reminder" key={item.id}><span className={`reminder-dot tone-${index % 3}`}><Bell size={16} /></span><div><strong>{item.title}</strong><small>{formatClock(item.remind_at)}{item.note ? ` · ${item.note}` : ""}</small></div></div>
              ))}
            </div>
          ) : <div className="soft-empty"><CalendarDays size={23} /><span><strong>近 7 天还没有提醒</strong><small>可以在成长页添加喂养、作息或疫苗提醒</small></span></div>}
          <Link href="/growth" className="text-link">查看全部提醒 <ArrowRight size={15} /></Link>
        </article>
      </section>

      <section className="content-grid">
        <div className="main-column">
          <div className="section-title"><div><span className="eyebrow">快捷记录</span><h2>记下此刻的小事</h2></div><Link href="/growth" className="text-link">+更多记录</Link></div>
          <div className="quick-grid">
            <Link href="/growth?type=feeding" className="quick-card peach"><span>奶</span><strong>喂养</strong><small>奶量·辅食</small></Link>
            <Link href="/growth?type=sleep" className="quick-card lavender"><span>月</span><strong>睡眠</strong><small>入睡·醒来</small></Link>
            <Link href="/growth?type=growth" className="quick-card mint"><span>量</span><strong>身高体重</strong><small>成长曲线</small></Link>
            <Link href="/growth?type=milestone" className="quick-card yellow"><span>星</span><strong>里程碑</strong><small>第一次</small></Link>
          </div>
          <article className="latest-card">
            <div className="section-heading compact"><div><span className="eyebrow">最新成长记录</span><h2>{latestEvent ? (latestEvent.title || eventLabel(latestEvent.type)) : "还没有成长记录"}</h2></div><span className="line-icon"><Sprout size={20} /></span></div>
            <p>{latestEvent ? (latestEvent.note || `一条${eventLabel(latestEvent.type)}记录，已收进 ${selected.nickname} 的成长时间线。`) : `从今天的第一项喂养、睡眠或里程碑开始，慢慢累积 ${selected.nickname} 的故事。`}</p>
            <Link href="/growth" className="text-link">{latestEvent ? "打开成长时间线" : "添加第一条记录"} <ArrowRight size={15} /></Link>
          </article>
        </div>

        <aside className="story-panel">
          <div className="story-art" style={{ backgroundImage: `linear-gradient(180deg, transparent 30%, rgba(42,54,51,.72)), url(${cover || "/illustrations/story-cover.jpg"})` }}>
            <span className="story-label"><BookOpen size={15} /> 今夜故事</span>
          </div>
          <div className="story-copy"><span className="eyebrow">故事工坊</span><h2>{latestStory?.title || "把孩子的小世界，变成今晚的故事"}</h2><p>{latestStory ? `“${latestStory.theme}”已收入 ${selected.nickname} 的书架。` : `用 ${selected.nickname} 喜欢的主题，生成一本可听、可读的个性化绘本。`}</p><Link href="/stories" className="button dark">{latestStory ? "去书架继续读" : "开始创作故事"} <ArrowRight size={17} /></Link></div>
        </aside>
      </section>

      <AdSlot page="home" ageBucket={selected ? ageBucket(selected.birth_date) : "1-3"} consent={true} isMember={isMember} />
      <footer className="safety-note"><CircleAlert size={16} /><span>知芽提供育儿信息参考，不代替医生诊断。如有窒息、意识丧失、抽搐等危急情况，请立即拨打 120。</span></footer>
      {dialogOpen && <ChildDialog onClose={() => setDialogOpen(false)} onCreated={(child) => { setDialogOpen(false); void loadDashboard(child.id); }} />}
    </div>
  );
}

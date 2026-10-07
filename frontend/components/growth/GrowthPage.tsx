"use client";

import Image from "next/image";
import {
  Bell,
  ChevronDown,
  CircleAlert,
  Droplets,
  Heart,
  ListTodo,
  LoaderCircle,
  Milk,
  Moon,
  Pencil,
  Plus,
  RefreshCw,
  Ruler,
  Sprout,
  Star,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChildDialog } from "@/components/ChildDialog";
import { api } from "@/lib/api";
import { ageLabel, dateLabel, eventDetail, eventLabel, formatClock, reminderLabel } from "@/lib/format";
import { cancelReminderNotification, requestNotificationPermission, syncAllReminderNotifications, syncReminderNotification } from "@/lib/notifications";
import type { AppError, Child, GrowthEvent, Reminder, TimelineGroup } from "@/lib/types";
import { EventDialog } from "./EventDialog";
import { ReminderDialog, type ReminderInitialDraft } from "./ReminderDialog";

const TYPE_ICONS: Record<string, typeof Milk> = {
  feeding: Milk,
  sleep: Moon,
  diaper: Droplets,
  growth: Ruler,
  milestone: Star,
  custom: Heart,
};

const FILTERS = ["all", "feeding", "sleep", "diaper", "growth", "milestone", "custom"] as const;

function eventIcon(type: string) {
  const Icon = TYPE_ICONS[type] ?? Heart;
  return <Icon size={17} />;
}

// 时间线只默认展示最近 5 天，更早的折叠
const RECENT_DAYS = 5;
function isRecentDate(dateStr: string): boolean {
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return false;
  const now = new Date();
  const cutoff = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (RECENT_DAYS - 1));
  return d >= cutoff;
}

export function GrowthPage() {
  const [children, setChildren] = useState<Child[]>([]);
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null);
  const [tab, setTab] = useState<"timeline" | "reminders">("timeline");
  const [groups, setGroups] = useState<TimelineGroup[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [filterType, setFilterType] = useState<string>("all");
  const [showAll, setShowAll] = useState(false);
  const [phase, setPhase] = useState<"loading" | "no-child" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [childDialogOpen, setChildDialogOpen] = useState(false);
  const [eventDialog, setEventDialog] = useState<{ open: boolean; event: GrowthEvent | null; initialType?: string; initialNote?: string }>({ open: false, event: null });
  const [reminderDialog, setReminderDialog] = useState<{ open: boolean; reminder: Reminder | null; initialDraft?: ReminderInitialDraft }>({ open: false, reminder: null });
  const pendingTypeRef = useRef<string | null>(null);
  const pendingNoteRef = useRef<string | null>(null);
  const pendingReminderRef = useRef<ReminderInitialDraft | null>(null);

  const selected = children.find((child) => child.id === selectedChildId) ?? null;

  const loadData = useCallback(async (childId: number) => {
    const [timelineResult, reminderResult] = await Promise.all([
      api.listTimeline(childId),
      api.listReminders(childId),
    ]);
    setGroups(timelineResult.groups);
    setReminders(reminderResult.items);
    void syncAllReminderNotifications(reminderResult.items);
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
          setGroups([]);
          setReminders([]);
          setPhase("no-child");
          return;
        }
        setSelectedChildId(targetId);
        window.localStorage.setItem("kids-mind-child-id", String(targetId));
        await loadData(targetId);
        const pendingType = pendingTypeRef.current;
        const pendingNote = pendingNoteRef.current;
        if (pendingType || pendingNote) {
          pendingTypeRef.current = null;
          pendingNoteRef.current = null;
          setEventDialog({ open: true, event: null, initialType: pendingType ?? undefined, initialNote: pendingNote ?? undefined });
        }
        const pendingReminder = pendingReminderRef.current;
        if (pendingReminder) {
          pendingReminderRef.current = null;
          setTab("reminders");
          setReminderDialog({ open: true, reminder: null, initialDraft: pendingReminder });
        }
      } catch (caught) {
        setError((caught as AppError).userMessage ?? "成长页暂时加载失败。");
        setPhase("error");
      }
    },
    [loadData],
  );

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const intent = params.get("intent");
    if (intent === "record") {
      const typeParam = params.get("type");
      if (typeParam && (FILTERS as readonly string[]).includes(typeParam) && typeParam !== "all") {
        pendingTypeRef.current = typeParam;
      }
      const note = params.get("note");
      if (note) pendingNoteRef.current = note;
      window.history.replaceState({}, "", window.location.pathname);
    } else if (intent === "reminder") {
      const draft: ReminderInitialDraft = {};
      const rt = params.get("type");
      if (rt && ["vaccine", "feeding", "routine", "custom"].includes(rt)) draft.type = rt;
      const title = params.get("title");
      if (title) draft.title = title;
      const note = params.get("note");
      if (note) draft.note = note;
      const time = params.get("time");
      if (time) draft.time = time;
      pendingReminderRef.current = draft;
      window.history.replaceState({}, "", window.location.pathname);
    } else {
      // 兼容原有 ?type= 快捷记录
      const typeParam = params.get("type");
      if (typeParam && (FILTERS as readonly string[]).includes(typeParam) && typeParam !== "all") {
        pendingTypeRef.current = typeParam;
        window.history.replaceState({}, "", window.location.pathname);
      }
    }
    const timer = window.setTimeout(() => void loadChildren(), 0);
    return () => window.clearTimeout(timer);
  }, [loadChildren]);

  function changeChild(id: number) {
    window.localStorage.setItem("kids-mind-child-id", String(id));
    setSelectedChildId(id);
    void loadData(id);
  }

  async function onEventSaved() {
    setEventDialog({ open: false, event: null });
    if (selectedChildId) await loadData(selectedChildId);
  }

  async function deleteEvent(event: GrowthEvent) {
    if (!window.confirm("确定删除这条记录吗？删除后无法恢复。")) return;
    try {
      await api.deleteEvent(event.id);
      if (selectedChildId) await loadData(selectedChildId);
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "删除失败，请稍后重试。");
    }
  }

  async function onReminderSaved(reminder: Reminder) {
    setReminderDialog({ open: false, reminder: null });
    await requestNotificationPermission();
    await syncReminderNotification(reminder);
    if (selectedChildId) await loadData(selectedChildId);
  }

  async function deleteReminder(reminder: Reminder) {
    if (!window.confirm("确定删除这条提醒吗？")) return;
    try {
      await api.deleteReminder(reminder.id);
      await cancelReminderNotification(reminder.id);
      if (selectedChildId) await loadData(selectedChildId);
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "删除失败，请稍后重试。");
    }
  }

  async function toggleReminder(reminder: Reminder) {
    try {
      const updated = await api.updateReminder(reminder.id, { enabled: !reminder.enabled });
      await syncReminderNotification(updated);
      if (selectedChildId) await loadData(selectedChildId);
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "更新失败，请稍后重试。");
    }
  }

  if (phase === "loading") {
    return <div className="page-state" role="status"><LoaderCircle className="spin" size={30} /><strong>正在整理成长记录…</strong><span>时间线和提醒很快就好</span></div>;
  }

  if (phase === "error") {
    return (
      <div className="page-state error-state"><CircleAlert size={30} /><strong>暂时没能连上服务</strong><span>{error}</span><button className="button secondary" onClick={() => void loadChildren()}><RefreshCw size={17} />重新连接</button></div>
    );
  }

  if (!selected) {
    return (
      <div className="empty-home">
        <div className="empty-visual"><span className="orbit one" /><span className="orbit two" /><Sprout size={48} /></div>
        <span className="eyebrow">成长</span>
        <h1>先建立档案，<br />再慢慢记下成长</h1>
        <p>喂养、睡眠、身高体重、里程碑，都会按日期收进时间线。</p>
        <button className="button primary large" onClick={() => setChildDialogOpen(true)}><Plus size={19} />建立成长档案</button>
        {childDialogOpen && <ChildDialog onClose={() => setChildDialogOpen(false)} onCreated={(child) => { setChildDialogOpen(false); void loadChildren(child.id); }} />}
      </div>
    );
  }

  const filteredGroups = filterType === "all"
    ? groups
    : groups.map((g) => ({ date: g.date, items: g.items.filter((item) => item.type === filterType) })).filter((g) => g.items.length > 0);

  const recentGroups = filteredGroups.filter((g) => isRecentDate(g.date));
  const olderGroups = filteredGroups.filter((g) => !isRecentDate(g.date));

  const renderGroup = (group: TimelineGroup) => (
    <div className="timeline-group" key={group.date}>
      <h3 className="timeline-date">{dateLabel(group.date)}<span>{group.date}</span></h3>
      <ul className="timeline-list">
        {group.items.map((event) => (
          <li className="timeline-item" key={event.id}>
            <span className={`event-icon tone-${event.type}`}>{eventIcon(event.type)}</span>
            <div className="event-copy">
              <div className="event-line"><span className="event-type">{eventLabel(event.type)}</span><strong>{eventDetail(event.type, event.data, event.title)}</strong></div>
              {event.note ? <p className="event-note">{event.note}</p> : null}
              <small className="event-time">{formatClock(event.occurred_at)}</small>
            </div>
            <div className="event-actions">
              <button className="icon-button" onClick={() => setEventDialog({ open: true, event })} aria-label="编辑记录"><Pencil size={16} /></button>
              <button className="icon-button danger" onClick={() => void deleteEvent(event)} aria-label="删除记录"><Trash2 size={16} /></button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );

  const enabledCount = reminders.filter((r) => r.enabled).length;

  return (
    <div className="growth-page">
      <header className="topbar">
        <div><p className="kicker">成长</p><h1><em>{selected.nickname}</em> 的成长足迹</h1></div>
        <div className="child-picker-wrap">
          <select className="child-picker" value={selected.id} onChange={(e) => changeChild(Number(e.target.value))} aria-label="切换孩子">
            {children.map((child) => <option key={child.id} value={child.id}>{child.nickname} · {ageLabel(child.birth_date)}</option>)}
          </select>
          <ChevronDown size={16} aria-hidden="true" />
          <button className="add-child" onClick={() => setChildDialogOpen(true)} aria-label="添加孩子"><Plus size={18} /></button>
        </div>
      </header>

      <nav className="growth-tabs" aria-label="成长页切换">
        <button className={tab === "timeline" ? "growth-tab active" : "growth-tab"} onClick={() => setTab("timeline")}><ListTodo size={16} />时间线</button>
        <button className={tab === "reminders" ? "growth-tab active" : "growth-tab"} onClick={() => setTab("reminders")}><Bell size={16} />提醒{reminders.length ? <span className="tab-count">{reminders.length}</span> : null}</button>
      </nav>

      {tab === "timeline" ? (
        <section className="timeline-panel">
          <div className="timeline-toolbar">
            <div className="filter-chips" role="tablist" aria-label="按类型筛选">
              <button className={filterType === "all" ? "chip active" : "chip"} onClick={() => setFilterType("all")}>全部</button>
              {FILTERS.slice(1).map((type) => (
                <button key={type} className={filterType === type ? "chip active" : "chip"} onClick={() => setFilterType(type)}>{eventLabel(type)}</button>
              ))}
            </div>
            <button className="button primary" onClick={() => setEventDialog({ open: true, event: null })}><Plus size={17} />记一笔</button>
          </div>

          {filteredGroups.length === 0 ? (
            <div className="soft-empty tall">
              <Image className="empty-illo" src="/illustrations/empty-state.jpg" alt="" width={180} height={135} />
              <span><strong>{filterType === "all" ? "还没有成长记录" : `还没有${eventLabel(filterType)}记录`}</strong><small>点右上角「记一笔」，第一件小事就开始了</small></span>
              <button className="button secondary" onClick={() => setEventDialog({ open: true, event: null, initialType: filterType === "all" ? undefined : filterType })}><Plus size={16} />记下此刻</button>
            </div>
          ) : (
            <>
              {recentGroups.map(renderGroup)}
              {olderGroups.length > 0 && (
                <button className="fold-toggle" onClick={() => setShowAll((v) => !v)}>
                  {showAll ? "收起更早记录" : `展开更早记录（${olderGroups.length} 天）`}
                </button>
              )}
              {showAll && olderGroups.map(renderGroup)}
            </>
          )}
        </section>
      ) : (
        <section className="reminder-panel">
          <div className="timeline-toolbar">
            <p className="reminder-summary">{reminders.length ? `共 ${reminders.length} 条 · 已开启 ${enabledCount} 条` : "提醒会帮你记得疫苗、喂养和作息"}</p>
            <button className="button primary" onClick={() => setReminderDialog({ open: true, reminder: null })}><Plus size={17} />添加提醒</button>
          </div>

          {reminders.length === 0 ? (
            <div className="soft-empty tall">
              <Image className="empty-illo" src="/illustrations/empty-state.jpg" alt="" width={180} height={135} />
              <span><strong>还没有提醒</strong><small>添加一条疫苗或作息提醒，就不会错过重要日子</small></span>
              <button className="button secondary" onClick={() => setReminderDialog({ open: true, reminder: null })}><Plus size={16} />添加提醒</button>
            </div>
          ) : (
            <ul className="reminder-list-full">
              {reminders.map((reminder) => (
                <li className={reminder.enabled ? "reminder-row" : "reminder-row muted"} key={reminder.id}>
                  <span className="reminder-row-icon"><Bell size={17} /></span>
                  <div className="reminder-row-copy">
                    <div className="event-line"><span className="event-type">{reminderLabel(reminder.type)}</span><strong>{reminder.title}</strong></div>
                    {reminder.note ? <p className="event-note">{reminder.note}</p> : null}
                    <small className="event-time">{formatClock(reminder.remind_at)}</small>
                  </div>
                  <div className="reminder-row-actions">
                    <button className={reminder.enabled ? "toggle on" : "toggle"} role="switch" aria-checked={reminder.enabled} aria-label="启用或停用" onClick={() => void toggleReminder(reminder)}><span /></button>
                    <button className="icon-button" onClick={() => setReminderDialog({ open: true, reminder })} aria-label="编辑提醒"><Pencil size={16} /></button>
                    <button className="icon-button danger" onClick={() => void deleteReminder(reminder)} aria-label="删除提醒"><Trash2 size={16} /></button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {childDialogOpen && <ChildDialog onClose={() => setChildDialogOpen(false)} onCreated={(child) => { setChildDialogOpen(false); void loadChildren(child.id); }} />}
      {eventDialog.open && (
        <EventDialog
          childId={selected.id}
          event={eventDialog.event}
          initialType={eventDialog.initialType}
          initialNote={eventDialog.initialNote}
          onClose={() => setEventDialog({ open: false, event: null })}
          onSaved={() => void onEventSaved()}
        />
      )}
      {reminderDialog.open && (
        <ReminderDialog
          childId={selected.id}
          reminder={reminderDialog.reminder}
          initialDraft={reminderDialog.initialDraft}
          onClose={() => setReminderDialog({ open: false, reminder: null })}
          onSaved={(reminder) => void onReminderSaved(reminder)}
        />
      )}
    </div>
  );
}

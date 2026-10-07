"use client";

import { X } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { defaultLocalDatetime, reminderLabel, toApiDatetime, toLocalInputValue } from "@/lib/format";
import type { AppError, Reminder, ReminderDraft, ReminderPatch } from "@/lib/types";

const REMINDER_TYPES = ["vaccine", "feeding", "routine", "custom"] as const;

export type ReminderInitialDraft = {
  type?: string;
  title?: string;
  note?: string;
  time?: string;
};

/** 把 "HH:MM" 拼到今天，得到 datetime-local 输入值。 */
function todayAtTime(time: string): string {
  const m = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(time);
  if (!m) return defaultLocalDatetime();
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${m[1]}:${m[2]}`;
}

export function ReminderDialog({
  childId,
  reminder,
  initialDraft,
  onClose,
  onSaved,
}: {
  childId: number;
  reminder?: Reminder | null;
  initialDraft?: ReminderInitialDraft;
  onClose: () => void;
  onSaved: (reminder: Reminder) => void;
}) {
  const [type, setType] = useState<string>(reminder?.type ?? initialDraft?.type ?? "vaccine");
  const [title, setTitle] = useState(reminder?.title ?? initialDraft?.title ?? "");
  const [note, setNote] = useState(reminder?.note ?? initialDraft?.note ?? "");
  const [remindAt, setRemindAt] = useState(
    reminder ? toLocalInputValue(reminder.remind_at) : initialDraft?.time ? todayAtTime(initialDraft.time) : defaultLocalDatetime(),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(eventForm: React.FormEvent<HTMLFormElement>) {
    eventForm.preventDefault();
    if (!title.trim() || !remindAt) {
      setError("请填写提醒标题和时间。");
      return;
    }
    setSaving(true);
    setError("");
    try {
      let saved: Reminder;
      if (reminder) {
        const patch: ReminderPatch = { title: title.trim(), note: note.trim() || undefined, remind_at: toApiDatetime(remindAt) };
        saved = await api.updateReminder(reminder.id, patch);
      } else {
        const draft: ReminderDraft = { type, title: title.trim(), note: note.trim() || undefined, remind_at: toApiDatetime(remindAt) };
        saved = await api.createReminder(childId, draft);
      }
      onSaved(saved);
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "保存失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="reminder-dialog-title" onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <div><span className="eyebrow">提醒</span><h2 id="reminder-dialog-title">{reminder ? "编辑提醒" : "添加提醒"}</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="关闭"><X size={20} /></button>
        </div>
        <form onSubmit={submit} className="child-form">
          <label>
            <span>提醒类型</span>
            <select value={type} onChange={(e) => setType(e.target.value)} disabled={!!reminder}>
              {REMINDER_TYPES.map((t) => <option key={t} value={t}>{reminderLabel(t)}</option>)}
            </select>
          </label>
          <label>
            <span>提醒内容 <b>*</b></span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={100} placeholder={type === "vaccine" ? "例如：五联疫苗第二针" : "例如：晚上 8 点喂奶"} autoFocus />
          </label>
          <label>
            <span>提醒时间 <b>*</b></span>
            <input type="datetime-local" value={remindAt} onChange={(e) => setRemindAt(e.target.value)} />
          </label>
          <label>
            <span>备注（可选）</span>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={200} placeholder="例如：接种前先量体温" />
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="dialog-actions">
            <button type="button" className="button ghost" onClick={onClose}>取消</button>
            <button className="button primary" disabled={saving}>{saving ? "正在保存…" : reminder ? "保存修改" : "添加提醒"}</button>
          </div>
        </form>
      </section>
    </div>
  );
}

"use client";

import { X } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { defaultLocalDatetime, eventLabel, toApiDatetime, toLocalInputValue } from "@/lib/format";
import type { AppError, EventDraft, GrowthEvent } from "@/lib/types";

const EVENT_TYPES = ["feeding", "sleep", "diaper", "growth", "milestone", "custom"] as const;

export function EventDialog({
  childId,
  event,
  initialType,
  initialNote,
  onClose,
  onSaved,
}: {
  childId: number;
  event?: GrowthEvent | null;
  initialType?: string;
  initialNote?: string;
  onClose: () => void;
  onSaved: (event: GrowthEvent) => void;
}) {
  const [type, setType] = useState<string>(event?.type ?? initialType ?? "feeding");
  const [title, setTitle] = useState(event?.title ?? "");
  const [note, setNote] = useState(event?.note ?? initialNote ?? "");
  const [occurredAt, setOccurredAt] = useState(
    event ? toLocalInputValue(event.occurred_at) : defaultLocalDatetime(),
  );
  const [amount, setAmount] = useState(typeof event?.data?.amount === "string" ? event.data.amount : "");
  const [duration, setDuration] = useState(typeof event?.data?.duration === "string" ? event.data.duration : "");
  const [kind, setKind] = useState(typeof event?.data?.kind === "string" ? event.data.kind : "正常");
  const [height, setHeight] = useState(event?.data?.height != null ? String(event.data.height) : "");
  const [weight, setWeight] = useState(event?.data?.weight != null ? String(event.data.weight) : "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function buildDraft(): EventDraft {
    const draft: EventDraft = {
      type,
      occurred_at: toApiDatetime(occurredAt),
      note: note.trim() || undefined,
    };
    if (type === "milestone" || type === "custom") {
      draft.title = title.trim() || undefined;
    }
    if (type === "feeding" && amount.trim()) draft.data = { amount: amount.trim() };
    if (type === "sleep" && duration.trim()) draft.data = { duration: duration.trim() };
    if (type === "diaper") draft.data = { kind };
    if (type === "growth") {
      const data: Record<string, unknown> = {};
      if (height.trim()) data.height = height.trim();
      if (weight.trim()) data.weight = weight.trim();
      if (Object.keys(data).length) draft.data = data;
    }
    return draft;
  }

  async function submit(eventForm: React.FormEvent<HTMLFormElement>) {
    eventForm.preventDefault();
    if (!occurredAt) {
      setError("请选择记录时间。");
      return;
    }
    if ((type === "milestone" || type === "custom") && !title.trim()) {
      setError("请填写这条记录的标题。");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const saved = event ? await api.updateEvent(event.id, buildDraft()) : await api.createEvent(childId, buildDraft());
      onSaved(saved);
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "保存失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  }

  const needsTitle = type === "milestone" || type === "custom";

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="event-dialog-title" onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <div><span className="eyebrow">成长记录</span><h2 id="event-dialog-title">{event ? "编辑记录" : "记下此刻"}</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="关闭"><X size={20} /></button>
        </div>
        <form onSubmit={submit} className="child-form">
          <label>
            <span>记录类型</span>
            <select value={type} onChange={(e) => setType(e.target.value)}>
              {EVENT_TYPES.map((t) => <option key={t} value={t}>{eventLabel(t)}</option>)}
            </select>
          </label>

          <label>
            <span>记录时间 <b>*</b></span>
            <input type="datetime-local" value={occurredAt} max={defaultLocalDatetime()} onChange={(e) => setOccurredAt(e.target.value)} />
          </label>

          {needsTitle && (
            <label>
              <span>标题 <b>*</b></span>
              <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={100} placeholder={type === "milestone" ? "例如：第一次翻身" : "例如：第一次去公园"} autoFocus />
            </label>
          )}

          {type === "feeding" && (
            <label><span>奶量 / 辅食</span><input value={amount} onChange={(e) => setAmount(e.target.value)} maxLength={50} placeholder="例如：120ml 或 半碗米粉" /></label>
          )}
          {type === "sleep" && (
            <label><span>睡了多久</span><input value={duration} onChange={(e) => setDuration(e.target.value)} maxLength={50} placeholder="例如：2 小时" /></label>
          )}
          {type === "diaper" && (
            <label><span>性状</span><select value={kind} onChange={(e) => setKind(e.target.value)}><option>正常</option><option>偏稀</option><option>偏干</option></select></label>
          )}
          {type === "growth" && (
            <div className="form-row">
              <label><span>身高（cm）</span><input value={height} onChange={(e) => setHeight(e.target.value)} inputMode="decimal" placeholder="例如：72.5" /></label>
              <label><span>体重（kg）</span><input value={weight} onChange={(e) => setWeight(e.target.value)} inputMode="decimal" placeholder="例如：9.2" /></label>
            </div>
          )}

          <label>
            <span>备注（可选）</span>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={500} placeholder="记下当时的小细节" />
          </label>

          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="dialog-actions">
            <button type="button" className="button ghost" onClick={onClose}>取消</button>
            <button className="button primary" disabled={saving}>{saving ? "正在保存…" : event ? "保存修改" : "保存记录"}</button>
          </div>
        </form>
      </section>
    </div>
  );
}

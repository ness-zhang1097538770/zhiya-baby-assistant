const EVENT_LABELS: Record<string, string> = {
  feeding: "喂养",
  sleep: "睡眠",
  diaper: "排便",
  growth: "身高体重",
  milestone: "里程碑",
  custom: "成长记录",
};

export function ageLabel(birthDate: string, now = new Date()): string {
  const birth = new Date(`${birthDate}T00:00:00`);
  if (Number.isNaN(birth.getTime()) || birth > now) return "年龄待补充";

  let months = (now.getFullYear() - birth.getFullYear()) * 12;
  months += now.getMonth() - birth.getMonth();
  if (now.getDate() < birth.getDate()) months -= 1;
  months = Math.max(0, months);

  if (months < 12) return `${months} 个月`;
  const years = Math.floor(months / 12);
  const rest = months % 12;
  return rest ? `${years} 岁 ${rest} 个月` : `${years} 岁`;
}

export function eventLabel(type: string): string {
  return EVENT_LABELS[type] ?? "成长记录";
}

export function formatClock(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间待确认";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function storyCover(images: unknown): string | null {
  if (!Array.isArray(images) || images.length === 0) return null;
  const first = images[0];
  if (typeof first === "string") return first;
  if (typeof first === "object" && first !== null) {
    const item = first as Record<string, unknown>;
    const value = item.url ?? item.path ?? item.image_url;
    return typeof value === "string" ? value : null;
  }
  return null;
}

export type RiskLevel = "L1" | "L2" | "L3" | "L4" | "NEED_MORE_INFO";

export function riskLabel(level?: string | null): string {
  switch (level) {
    case "L1": return "危急";
    case "L2": return "紧急";
    case "L3": return "观察";
    case "L4": return "常规";
    case "NEED_MORE_INFO": return "需要补充信息";
    default: return "育儿建议";
  }
}

export function riskTone(level?: string | null): string {
  switch (level) {
    case "L1": return "risk-l1";
    case "L2": return "risk-l2";
    case "L3": return "risk-l3";
    case "L4": return "risk-l4";
    default: return "risk-info";
  }
}

export function formatTime(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  return new Intl.DateTimeFormat("zh-CN", sameDay ? { hour: "2-digit", minute: "2-digit", hour12: false } : { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}

const REMINDER_LABELS: Record<string, string> = {
  vaccine: "疫苗",
  feeding: "喂养",
  routine: "作息",
  custom: "自定义",
};

export function reminderLabel(type: string): string {
  return REMINDER_LABELS[type] ?? "提醒";
}

/** 事件的展示摘要：优先取结构化 data，其次标题。 */
export function eventDetail(type: string, data?: Record<string, unknown> | null, title?: string | null): string {
  switch (type) {
    case "feeding": {
      const amount = data?.amount;
      return typeof amount === "string" && amount ? amount : title || "喂养记录";
    }
    case "sleep": {
      const duration = data?.duration;
      return typeof duration === "string" && duration ? duration : title || "睡眠记录";
    }
    case "diaper": {
      const kind = data?.kind;
      return typeof kind === "string" && kind ? kind : title || "排便记录";
    }
    case "growth": {
      const h = data?.height;
      const w = data?.weight;
      const parts: string[] = [];
      if (typeof h === "number" || (typeof h === "string" && h)) parts.push(`身高 ${h} cm`);
      if (typeof w === "number" || (typeof w === "string" && w)) parts.push(`体重 ${w} kg`);
      return parts.length ? parts.join(" · ") : title || "身高体重记录";
    }
    case "milestone":
    case "custom":
      return title || "成长记录";
    default:
      return title || "成长记录";
  }
}

/** 时间线分组日期标签：今天/昨天/具体日期。 */
export function dateLabel(value: string, now = new Date()): string {
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const that = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diff = Math.round((today.getTime() - that.getTime()) / 86400000);
  if (diff === 0) return "今天";
  if (diff === 1) return "昨天";
  return new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(d);
}

/** datetime-local 值转后端可解析的 ISO 时间（补齐秒）。 */
export function toApiDatetime(local: string): string {
  if (!local) return local;
  return local.length === 16 ? `${local}:00` : local;
}

/** 当前时间的 datetime-local 默认值（用于表单）。 */
export function defaultLocalDatetime(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

/** ISO 时间转 datetime-local 输入值。 */
export function toLocalInputValue(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const STORY_STATUS_LABELS: Record<string, string> = {
  character_generating: "设计角色中",
  character_ready: "待确认角色",
  outline_generating: "生成大纲中",
  outline_ready: "待确认大纲",
  content_generating: "生成正文中",
  content_ready: "待生成插画",
  assets_generating: "生成插画朗读中",
  ready: "已完成",
  failed: "生成失败",
  cancelled: "已取消",
};

export function storyStatusLabel(status: string): string {
  return STORY_STATUS_LABELS[status] ?? status;
}

/** 是否处于生成中的状态（需要轮询）。 */
export function isStoryRunning(status: string): boolean {
  return status === "character_generating" || status === "outline_generating" || status === "content_generating" || status === "assets_generating";
}

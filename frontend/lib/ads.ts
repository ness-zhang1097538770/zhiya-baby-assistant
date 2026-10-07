// 广告：硬屏蔽规则 + 取广告 + 事件上报（商业化 C-2 批次，不上真实投放）。
// 铁律三：广告只买「场景」，不能买「答案」。前端隐藏不算权限，后端再挡一道。
import { getToken } from "./auth";

export type AdItem = {
  ad_id: number;
  advertiser: string;
  title?: string | null;
  slot: string;
  age_bucket?: string | null;
  image_url?: string | null;
  landing_url?: string | null;
};

export type AdBlockContext = {
  riskLevel?: string | null;
  medical?: boolean;
  isMember?: boolean;
};

const RISK_SHIELD = new Set(["L1", "L2", "L3"]);
const DEVICE_KEY = "kids-mind-device-id";

/** 硬屏蔽四规则之一、二、三（前端）：风险页 / 医疗会话 / 会员 均不展示广告。 */
export function shouldShowAd(ctx: AdBlockContext): boolean {
  if (RISK_SHIELD.has(ctx.riskLevel ?? "")) return false;
  if (ctx.medical) return false;
  if (ctx.isMember) return false;
  return true;
}

/** 匿名设备 ID：localStorage 生成一次，广告日志维度，不关联 child_id。 */
export function getDeviceId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `dev-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    window.localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

export async function fetchAds(params: {
  page: string;
  ageBucket: string;
  consent: boolean;
  riskLevel?: string | null;
  medical?: boolean;
}): Promise<AdItem[]> {
  const q = new URLSearchParams({
    page: params.page,
    age_bucket: params.ageBucket,
    consent: String(params.consent),
    device_id: getDeviceId(),
  });
  if (params.riskLevel) q.set("risk_level", params.riskLevel);
  if (params.medical) q.set("medical", "true");
  try {
    const res = await fetch(`/api/v1/ads?${q.toString()}`, {
      headers: authHeaders(),
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as { ads?: AdItem[] };
    return data.ads ?? [];
  } catch {
    return [];
  }
}

export async function logAdEvent(payload: {
  slot: string;
  action: "impression" | "click" | "close" | "report";
  adId?: number | null;
  ageBucket?: string | null;
}): Promise<void> {
  try {
    await fetch("/api/v1/ads/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_id: getDeviceId(),
        ad_id: payload.adId ?? null,
        slot: payload.slot,
        age_bucket: payload.ageBucket ?? null,
        action: payload.action,
      }),
    });
  } catch {
    // 埋点失败不阻断业务
  }
}

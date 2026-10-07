// 产品行为埋点：登录态上报到后端（后端从 token 取 family_id，匿名维度带 device_id）。
import { getDeviceId } from "./ads";
import { getToken } from "./auth";

/** 组装埋点载荷（纯函数，便于测试）。 */
export function buildEventPayload(event: string, props?: Record<string, unknown>) {
  return { device_id: getDeviceId(), event, props: props ?? null };
}

/** 上报一条产品行为事件；埋点失败不阻断业务。 */
export async function track(event: string, props?: Record<string, unknown>): Promise<void> {
  const token = getToken();
  if (!token) return;
  try {
    await fetch("/api/v1/analytics/events", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(buildEventPayload(event, props)),
    });
  } catch {
    // 埋点失败不阻断业务
  }
}

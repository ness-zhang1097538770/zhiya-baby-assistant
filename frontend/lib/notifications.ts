import type { Reminder } from "./types";

/**
 * 纯函数：判断一条提醒是否需要在本机排一个到点通知。
 * 便于单测；实际插件调用是薄封装。
 */
export function reminderNotificationDecision(
  reminder: Pick<Reminder, "enabled" | "remind_at">,
  now = new Date(),
): { schedule: boolean; at: Date } {
  const at = new Date(reminder.remind_at);
  const valid = !Number.isNaN(at.getTime());
  const future = valid && at.getTime() > now.getTime();
  return { schedule: Boolean(reminder.enabled) && future, at };
}

type LocalNotificationsBridge = {
  schedule: (options: { id: number; title: string; body: string; at: Date }) => Promise<void>;
  cancel: (id: number) => Promise<void>;
  requestPermission: () => Promise<boolean>;
};

let bridgePromise: Promise<LocalNotificationsBridge | null> | null = null;

function isNative(): boolean {
  const w = window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } };
  return Boolean(w.Capacitor?.isNativePlatform?.());
}

async function loadBridge(): Promise<LocalNotificationsBridge | null> {
  if (!isNative()) return null;
  try {
    const { LocalNotifications } = await import("@capacitor/local-notifications");
    return {
      async schedule({ id, title, body, at }) {
        await LocalNotifications.schedule({
          notifications: [{ id, title, body, schedule: { at, allowWhileIdle: true } }],
        });
      },
      async cancel(id) {
        await LocalNotifications.cancel({ notifications: [{ id }] });
      },
      async requestPermission() {
        const result = await LocalNotifications.requestPermissions();
        return result.display === "granted";
      },
    };
  } catch {
    return null;
  }
}

function getBridge(): Promise<LocalNotificationsBridge | null> {
  if (!bridgePromise) bridgePromise = loadBridge();
  return bridgePromise;
}

export async function requestNotificationPermission(): Promise<boolean> {
  const bridge = await getBridge();
  if (!bridge) return false;
  try {
    return await bridge.requestPermission();
  } catch {
    return false;
  }
}

export async function syncReminderNotification(reminder: Reminder): Promise<void> {
  const bridge = await getBridge();
  if (!bridge) return;
  const { schedule, at } = reminderNotificationDecision(reminder);
  try {
    if (schedule) {
      await bridge.schedule({
        id: reminder.id,
        title: reminder.title,
        body: `到点提醒${reminder.note ? ` · ${reminder.note}` : "，别忘了这件事"}`,
        at,
      });
    } else {
      await bridge.cancel(reminder.id);
    }
  } catch {
    // 通知排程失败不影响主流程（纯 web 环境或无权限时静默跳过）
  }
}

export async function syncAllReminderNotifications(reminders: Reminder[]): Promise<void> {
  const bridge = await getBridge();
  if (!bridge) return;
  const now = new Date();
  for (const reminder of reminders) {
    const { schedule, at } = reminderNotificationDecision(reminder, now);
    try {
      if (schedule) {
        await bridge.schedule({
          id: reminder.id,
          title: reminder.title,
          body: `到点提醒${reminder.note ? ` · ${reminder.note}` : "，别忘了这件事"}`,
          at,
        });
      } else {
        await bridge.cancel(reminder.id);
      }
    } catch {
      // 继续下一条
    }
  }
}

export async function cancelReminderNotification(id: number): Promise<void> {
  const bridge = await getBridge();
  if (!bridge) return;
  try {
    await bridge.cancel(id);
  } catch {
    // 静默跳过
  }
}

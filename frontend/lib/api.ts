import { clearToken, getToken } from "./auth";
import type {
  AgentResult,
  AppError,
  Child,
  ChildDraft,
  ChildFact,
  CompanionScript,
  ConversationHistory,
  ConversationSummary,
  EmotionResult,
  Entitlements,
  EventDraft,
  FactUpdate,
  GrowthEvent,
  IntentResult,
  QADone,
  Reminder,
  ReminderDraft,
  ReminderPatch,
  Story,
  StoryCharacter,
  StoryDraft,
  StoryOutline,
  TimelineGroup,
} from "./types";

function authHeaders(): Record<string, string> {
  const token = getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

function handleUnauthorized(status: number): void {
  if (status === 401) {
    clearToken();
    window.location.replace("/");
  }
}

type Items<T> = { items: T[] };

export type StreamEvent =
  | { type: "chunk"; text: string }
  | { type: "done"; data: QADone }
  | { type: "error"; code: string; message: string; conversation_id?: number };

function asAppError(error: unknown): AppError {
  if (typeof error === "object" && error !== null && "userMessage" in error) {
    return error as AppError;
  }
  const isTimeout = error instanceof DOMException && error.name === "AbortError";
  return {
    code: isTimeout ? "REQUEST_TIMEOUT" : "NETWORK_ERROR",
    message: isTimeout ? "请求超时" : "网络连接失败",
    userMessage: isTimeout
      ? "连接服务超时，请稍后再试。"
      : "暂时连接不上服务，请确认后端已启动后重试。",
    retryable: true,
  };
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12_000);

  try {
    const response = await fetch(path, {
      ...init,
      headers: authHeaders(),
      signal: controller.signal,
      cache: "no-store",
    });

    if (!response.ok) {
      handleUnauthorized(response.status);
      let code = `HTTP_${response.status}`;
      let message = "请求没有成功";
      try {
        const body = (await response.json()) as {
          error?: { code?: string; message?: string };
          detail?: { error?: { code?: string; message?: string } };
        };
        const error = body.error ?? body.detail?.error;
        code = error?.code ?? code;
        message = error?.message ?? message;
      } catch {
        // Keep the safe fallback instead of exposing an upstream response.
      }
      const appError: AppError = {
        code,
        message,
        userMessage: message,
        retryable: response.status >= 500,
      };
      throw appError;
    }

    return (await response.json()) as T;
  } catch (error) {
    throw asAppError(error);
  } finally {
    window.clearTimeout(timeout);
  }
}

function parseSSEBlock(block: string): StreamEvent | null {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice("event:".length).trim();
    else if (line.startsWith("data:")) data += line.slice("data:".length).trim();
  }
  if (!data) return null;
  try {
    const parsed = JSON.parse(data) as unknown;
    if (event === "chunk") {
      const text = typeof parsed === "object" && parsed !== null && "text" in parsed ? String((parsed as { text: unknown }).text ?? "") : "";
      return { type: "chunk", text };
    }
    if (event === "done") return { type: "done", data: parsed as QADone };
    if (event === "error") {
      const parsedObj = typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : {};
      const err = parsedObj.error as { code?: string; message?: string } | undefined;
      const conversationId = typeof parsedObj.conversation_id === "number" ? parsedObj.conversation_id : undefined;
      return { type: "error", code: err?.code ?? "GENERATION_ERROR", message: err?.message ?? "生成失败，请稍后重试。", conversation_id: conversationId };
    }
    return null;
  } catch {
    return null;
  }
}

async function apiDelete(path: string): Promise<void> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12_000);
  try {
    const response = await fetch(path, {
      method: "DELETE",
      headers: authHeaders(),
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) {
      handleUnauthorized(response.status);
      let code = `HTTP_${response.status}`;
      let message = "请求没有成功";
      try {
        const body = (await response.json()) as {
          error?: { code?: string; message?: string };
          detail?: { error?: { code?: string; message?: string } };
        };
        const error = body.error ?? body.detail?.error;
        code = error?.code ?? code;
        message = error?.message ?? message;
      } catch {
        // Keep the safe fallback.
      }
      throw { code, message, userMessage: message, retryable: response.status >= 500 } as AppError;
    }
  } catch (error) {
    throw asAppError(error);
  } finally {
    window.clearTimeout(timeout);
  }
}

async function streamQA(
  payload: { child_id: number; question: string; conversation_id?: number | null },
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 60_000);
  try {
    const response = await fetch("/api/v1/qa", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(payload),
      signal: controller.signal,
      cache: "no-store",
    });

    if (!response.ok || !response.body) {
      handleUnauthorized(response.status);
      let code = `HTTP_${response.status}`;
      let message = "请求没有成功";
      try {
        const body = (await response.json()) as {
          error?: { code?: string; message?: string };
          detail?: { error?: { code?: string; message?: string } };
        };
        const error = body.error ?? body.detail?.error;
        code = error?.code ?? code;
        message = error?.message ?? message;
      } catch {
        // Keep the safe fallback.
      }
      throw { code, message, userMessage: message, retryable: response.status >= 500 } as AppError;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        const event = parseSSEBlock(part);
        if (event) onEvent(event);
      }
    }
    if (buffer.trim()) {
      const event = parseSSEBlock(buffer);
      if (event) onEvent(event);
    }
  } catch (error) {
    throw asAppError(error);
  } finally {
    window.clearTimeout(timeout);
  }
}

async function uploadStoryPhoto(file: File): Promise<{ character_image: string }> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 90_000);  // 图生图较慢
  try {
    const formData = new FormData();
    formData.append("file", file);
    const token = getToken();
    const response = await fetch("/api/v1/stories/photo", {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
      signal: controller.signal,
    });
    if (!response.ok) {
      handleUnauthorized(response.status);
      let message = "照片处理失败";
      try {
        const body = (await response.json()) as { error?: { message?: string }; detail?: { error?: { message?: string } } };
        const error = body.error ?? body.detail?.error;
        message = error?.message ?? message;
      } catch {
        // keep safe fallback
      }
      throw { code: "PHOTO_FAILED", message, userMessage: message, retryable: false } as AppError;
    }
    return (await response.json()) as { character_image: string };
  } catch (error) {
    throw asAppError(error);
  } finally {
    window.clearTimeout(timeout);
  }
}

async function uploadAvatar(childId: number, file: File): Promise<{ avatar: string }> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 30_000);
  try {
    const formData = new FormData();
    formData.append("file", file);
    const token = getToken();
    const response = await fetch(`/api/v1/children/${childId}/avatar`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
      signal: controller.signal,
    });
    if (!response.ok) {
      handleUnauthorized(response.status);
      let message = "上传失败";
      try {
        const body = (await response.json()) as { error?: { message?: string }; detail?: { error?: { message?: string } } };
        const error = body.error ?? body.detail?.error;
        message = error?.message ?? message;
      } catch {
        // keep safe fallback
      }
      throw { code: "UPLOAD_FAILED", message, userMessage: message, retryable: false } as AppError;
    }
    return (await response.json()) as { avatar: string };
  } catch (error) {
    throw asAppError(error);
  } finally {
    window.clearTimeout(timeout);
  }
}

async function login(inviteCode: string): Promise<{ token: string; family_id: number }> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12_000);
  try {
    const response = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ invite_code: inviteCode }),
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) {
      let code = `HTTP_${response.status}`;
      let message = "登录失败";
      try {
        const body = (await response.json()) as {
          error?: { code?: string; message?: string };
          detail?: { error?: { code?: string; message?: string } };
        };
        const error = body.error ?? body.detail?.error;
        code = error?.code ?? code;
        message = error?.message ?? message;
      } catch {
        // keep safe fallback
      }
      throw { code, message, userMessage: message, retryable: false } as AppError;
    }
    return (await response.json()) as { token: string; family_id: number };
  } catch (error) {
    throw asAppError(error);
  } finally {
    window.clearTimeout(timeout);
  }
}

export const api = {
  login,
  listChildren: () => apiRequest<Items<Child>>("/api/v1/children"),
  createChild: (draft: ChildDraft) =>
    apiRequest<Child>("/api/v1/children", {
      method: "POST",
      body: JSON.stringify(draft),
    }),
  updateChild: (childId: number, draft: ChildDraft) =>
    apiRequest<Child>(`/api/v1/children/${childId}`, {
      method: "PUT",
      body: JSON.stringify(draft),
    }),
  deleteChild: (childId: number) => apiDelete(`/api/v1/children/${childId}`),
  uploadAvatar,
  uploadStoryPhoto,
  listUpcomingReminders: (childId: number) =>
    apiRequest<Items<Reminder>>(`/api/v1/children/${childId}/reminders/upcoming?days=7`),
  listEvents: (childId: number) =>
    apiRequest<Items<GrowthEvent>>(`/api/v1/children/${childId}/events`),
  listTimeline: (childId: number, type?: string) =>
    apiRequest<{ groups: TimelineGroup[] }>(
      `/api/v1/children/${childId}/timeline${type ? `?type=${encodeURIComponent(type)}` : ""}`,
    ),
  createEvent: (childId: number, draft: EventDraft) =>
    apiRequest<GrowthEvent>(`/api/v1/children/${childId}/events`, {
      method: "POST",
      body: JSON.stringify(draft),
    }),
  updateEvent: (eventId: number, draft: EventDraft) =>
    apiRequest<GrowthEvent>(`/api/v1/events/${eventId}`, {
      method: "PUT",
      body: JSON.stringify(draft),
    }),
  deleteEvent: (eventId: number) => apiDelete(`/api/v1/events/${eventId}`),
  listReminders: (childId: number) =>
    apiRequest<Items<Reminder>>(`/api/v1/children/${childId}/reminders`),
  createReminder: (childId: number, draft: ReminderDraft) =>
    apiRequest<Reminder>(`/api/v1/children/${childId}/reminders`, {
      method: "POST",
      body: JSON.stringify(draft),
    }),
  updateReminder: (reminderId: number, patch: ReminderPatch) =>
    apiRequest<Reminder>(`/api/v1/reminders/${reminderId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  deleteReminder: (reminderId: number) => apiDelete(`/api/v1/reminders/${reminderId}`),
  listFacts: (childId: number) =>
    apiRequest<Items<ChildFact>>(`/api/v1/children/${childId}/facts`),
  updateFact: (factId: number, patch: FactUpdate) =>
    apiRequest<ChildFact>(`/api/v1/facts/${factId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  deleteFact: (factId: number) => apiDelete(`/api/v1/facts/${factId}`),
  listStories: (childId: number) =>
    apiRequest<Items<Story>>(`/api/v1/children/${childId}/stories`),
  getStory: (storyId: number) => apiRequest<Story>(`/api/v1/stories/${storyId}`),
  createStory: (childId: number, draft: StoryDraft) =>
    apiRequest<Story>(`/api/v1/children/${childId}/stories`, {
      method: "POST",
      body: JSON.stringify(draft),
    }),
  confirmStoryCharacter: (storyId: number, character?: StoryCharacter) =>
    apiRequest<Story>(`/api/v1/stories/${storyId}/confirm-character`, {
      method: "POST",
      body: JSON.stringify(character ? { character } : {}),
    }),
  regenerateCharacterImage: (storyId: number, payload?: { look?: string; art_style?: string }) =>
    apiRequest<Story>(`/api/v1/stories/${storyId}/regenerate-character-image`, {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    }),
  regenerateOutline: (storyId: number) =>
    apiRequest<Story>(`/api/v1/stories/${storyId}/regenerate-outline`, {
      method: "POST",
      body: "{}",
    }),
  confirmStory: (storyId: number, outline?: StoryOutline) =>
    apiRequest<Story>(`/api/v1/stories/${storyId}/confirm`, {
      method: "POST",
      body: JSON.stringify(outline ? { outline } : {}),
    }),
  generateStoryAssets: (storyId: number) =>
    apiRequest<Story>(`/api/v1/stories/${storyId}/assets`, { method: "POST", body: "{}" }),
  cancelStory: (storyId: number) =>
    apiRequest<Story>(`/api/v1/stories/${storyId}/cancel`, { method: "POST", body: "{}" }),
  deleteStory: (storyId: number) => apiDelete(`/api/v1/stories/${storyId}`),
  listConversations: (childId: number) =>
    apiRequest<Items<ConversationSummary>>(`/api/v1/qa/conversations?child_id=${childId}`),
  getConversation: (conversationId: number) =>
    apiRequest<ConversationHistory>(`/api/v1/qa/conversations/${conversationId}`),
  deleteConversation: (conversationId: number) =>
    apiDelete(`/api/v1/qa/conversations/${conversationId}`),
  deleteAllConversations: (childId: number) =>
    apiDelete(`/api/v1/qa/conversations?child_id=${childId}`),
  askQuestion: streamQA,
  analyzeEmotion: (text: string) =>
    apiRequest<EmotionResult>("/api/v1/companion/analyze", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  generateCompanion: (payload: { mode: string; child_nickname?: string; situation?: string; gender?: string }) =>
    apiRequest<CompanionScript>("/api/v1/companion/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  classifyIntent: (text: string, childId: number) =>
    apiRequest<IntentResult>("/api/v1/intent/classify", {
      method: "POST",
      body: JSON.stringify({ text, child_id: childId }),
    }),
  runAgent: (text: string, childId: number) =>
    apiRequest<AgentResult>("/api/v1/agent/run", {
      method: "POST",
      body: JSON.stringify({ text, child_id: childId }),
    }),
  getEntitlements: () => apiRequest<Entitlements>("/api/v1/billing/entitlements"),
  subscribe: (source: string) =>
    apiRequest<{ plan: string; status: string; source: string; period_end: string | null }>(
      "/api/v1/billing/subscribe",
      { method: "POST", body: JSON.stringify({ source }) },
    ),
  redeem: (code: string) =>
    apiRequest<{ plan: string; status: string; source: string; period_end: string | null }>(
      "/api/v1/billing/redeem",
      { method: "POST", body: JSON.stringify({ code }) },
    ),
  purchase: (sku: string) =>
    apiRequest<{ id: number; kind: string; total: number; used: number }>(
      "/api/v1/billing/purchase",
      { method: "POST", body: JSON.stringify({ sku }) },
    ),
  cancelRenew: () =>
    apiRequest<{ plan: string; status: string; auto_renew: boolean }>(
      "/api/v1/billing/cancel-renew",
      { method: "POST", body: "{}" },
    ),
};

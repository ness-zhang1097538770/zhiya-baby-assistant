export type Child = {
  id: number;
  nickname: string;
  birth_date: string;
  gender?: string | null;
  feeding_method?: string | null;
  allergy_history?: string | null;
  premature?: string | null;
  avatar?: string | null;
};

export type ChildFact = {
  id: number;
  child_id: number;
  category: string;
  category_label: string;
  key: string;
  value: string;
  source: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type FactUpdate = {
  category?: string;
  key?: string;
  value?: string;
};

export type Reminder = {
  id: number;
  child_id: number;
  type: string;
  title: string;
  note?: string | null;
  remind_at: string;
  enabled: boolean;
};

export type GrowthEvent = {
  id: number;
  child_id: number;
  type: string;
  title?: string | null;
  note?: string | null;
  occurred_at: string;
  data?: Record<string, unknown> | null;
};

export type TimelineGroup = {
  date: string;
  items: GrowthEvent[];
};

export type EventDraft = {
  type: string;
  title?: string;
  note?: string;
  occurred_at: string;
  data?: Record<string, unknown>;
};

export type ReminderDraft = {
  type: string;
  title: string;
  note?: string;
  remind_at: string;
  repeat?: string;
};

export type ReminderPatch = {
  title?: string;
  note?: string;
  remind_at?: string;
  enabled?: boolean;
};

export type EmotionResult = {
  emotion: string;
  mode: string;
  suggestion: string;
};

export type CompanionScript = {
  title: string;
  segments: string[];
  breathing: { in: number; out: number };
  audio_url: string;
};

export type StoryCharacter = {
  hero: { name: string; look: string; personality: string };
  companions: { name: string; look: string; personality: string }[];
  art_style: string;
};

export type StoryOutlinePage = { page_no: number; outline: string };
export type StoryOutline = { title: string; pages: StoryOutlinePage[] };
export type StoryPage = { page_no: number; text: string; narration: string; image_prompt: string };
export type StoryAsset = { page_no: number; url: string };

export type Story = {
  id: number;
  child_id: number;
  title?: string | null;
  character_name: string;
  character_tags?: string | null;
  gender?: string | null;
  theme: string;
  age_range?: string | null;
  duration?: string | null;
  education_goal?: string | null;
  family_memory?: string | null;
  status: string;
  character?: StoryCharacter | null;
  character_image?: string | null;
  outline?: StoryOutline | null;
  pages?: { pages: StoryPage[] } | null;
  images?: StoryAsset[] | null;
  audio?: StoryAsset[] | null;
  error?: string | null;
  created_at?: string | null;
};

export type StoryDraft = {
  character_name: string;
  character_tags?: string;
  gender?: string;
  theme: string;
  age_range?: string;
  duration?: string;
  education_goal?: string;
  family_memory?: string;
  character_image?: string;
};

export type ChildDraft = {
  nickname: string;
  birth_date: string;
  gender?: string;
  feeding_method?: string;
  allergy_history?: string;
  premature?: string;
};

export type AppError = {
  code: string;
  message: string;
  userMessage: string;
  retryable: boolean;
};

export type Source = {
  id: number;
  title: string;
  source: string;
  version?: string | null;
  review_status?: string;
};

export type QADone = {
  conversation_id: number;
  risk_level: string;
  answer: string;
  conclusion: string;
  actions: string[];
  evidence: string[];
  red_flags: string[];
  disclaimer: string;
  followup_question?: string | null;
  followup_count: number;
  sources: Source[];
};

export type QAMessage = {
  role: "user" | "assistant";
  content: string;
  risk_level?: string | null;
  sources?: Source[];
  followup_question?: string | null;
  created_at?: string | null;
};

export type ConversationSummary = {
  id: number;
  child_id: number;
  title: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ConversationHistory = {
  conversation_id: number;
  child_id: number;
  messages: QAMessage[];
};

export type IntentResult = {
  intent: "ask" | "record" | "reminder" | "story" | "unknown";
  params: Record<string, unknown>;
};

export type AgentExecutedItem = { tool: string; summary: string };
export type AgentPendingItem = { tool: string; summary: string; params: Record<string, unknown> };
export type AgentResult = {
  intent: "ask" | "action" | "need_info" | "unknown";
  reply: string;
  followup_question?: string | null;
  params: Record<string, unknown>;
  executed: AgentExecutedItem[];
  pending: AgentPendingItem[];
};

export type Entitlements = {
  plan: "free" | "monthly" | "yearly" | "trial";
  status: string;
  source: string;
  period_end?: string | null;
  auto_renew: boolean;
  story_books_available: number;
  entitlements: {
    qa_daily_limit: number;
    story_monthly_grant: number;
    bookshelf_limit: number | null;
    memory_months: number | null;
    ai_insight: boolean;
    multi_child: boolean;
    long_answer: boolean;
    ads: boolean;
  };
};

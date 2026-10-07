"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, BellRing, BookOpen, Check, Clock, HelpCircle, LoaderCircle, PlusCircle, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { AgentResult, AppError } from "@/lib/types";

type Props = { childId: number };

const FALLBACK_ENTRIES = [
  { label: "问育儿", desc: "育儿问题、疫苗、辅食", href: "/ask", Icon: HelpCircle },
  { label: "记成长", desc: "喂养、睡眠、里程碑", href: "/growth", Icon: PlusCircle },
  { label: "设提醒", desc: "喂养、疫苗、作息", href: "/growth?tab=reminders", Icon: BellRing },
  { label: "讲故事", desc: "生成个性化绘本", href: "/stories", Icon: BookOpen },
];

export function IntentBar({ childId }: Props) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AgentResult | null>(null);
  const [showFallback, setShowFallback] = useState(false);
  const [followup, setFollowup] = useState<{ question: string; context: string } | null>(null);

  function routeAsk(question: string) {
    const sp = new URLSearchParams();
    sp.set("q", question);
    router.push(`/ask?${sp.toString()}`);
  }

  function routeStory(theme?: string) {
    const sp = new URLSearchParams();
    if (theme) sp.set("theme", theme);
    router.push(`/stories?${sp.toString()}`);
  }

  async function run(q: string) {
    setBusy(true);
    setError("");
    setResult(null);
    setShowFallback(false);
    setFollowup(null);
    try {
      const res = await api.runAgent(q, childId);
      if (res.intent === "ask") {
        routeAsk(String(res.params.question ?? q));
        return;
      }
      if (res.intent === "action") {
        setResult(res);
        setText("");
        return;
      }
      if (res.intent === "need_info") {
        // Agent Loop 追问：把当前完整上下文带下去，等用户补充后一次性再办
        setFollowup({ question: res.followup_question ?? "你具体想让我做什么呢？", context: q });
        setText("");
        return;
      }
      setShowFallback(true);
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "暂时没能理解这句话，请直接点下面入口。");
      setShowFallback(true);
    } finally {
      setBusy(false);
    }
  }

  function submit() {
    const q = text.trim();
    if (!q || busy) return;
    void run(q);
  }

  function submitFollowup() {
    const answer = text.trim();
    if (!answer || busy || !followup) return;
    void run(`${followup.context}。${answer}`);
  }

  function cancelFollowup() {
    setFollowup(null);
    setText("");
    setShowFallback(true);
  }

  return (
    <section className="intent-bar" aria-label="一句话入口">
      <div className="intent-heading">
        <span className="intent-spark"><Sparkles size={16} /></span>
        <span>{followup ? followup.question : "说一句话，我来帮你办"}</span>
      </div>
      <form
        className="intent-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (followup) void submitFollowup();
          else void submit();
        }}
      >
        <input
          className="intent-input"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder={followup ? "补充一下，比如：喝了150ml奶" : "比如：宝宝下午三点要喝奶"}
          disabled={busy}
          aria-label="一句话描述你想做的事"
        />
        <button className="intent-submit" type="submit" disabled={busy || !text.trim()}>
          {busy ? <LoaderCircle className="spin" size={17} /> : <ArrowRight size={17} />}
          <span>{busy ? "办理中" : followup ? "补充" : "走起"}</span>
        </button>
      </form>

      {followup && (
        <button className="intent-followup-cancel" onClick={cancelFollowup}>取消，换个方式</button>
      )}

      {error && <p className="intent-error">{error}</p>}

      {result && (
        <div className="intent-result" role="status" aria-live="polite">
          {result.reply && <p className="intent-result-reply">{result.reply}</p>}
          {result.executed.length > 0 && (
            <ul className="intent-result-list">
              {result.executed.map((item, index) => (
                <li key={index} className="intent-done-item">
                  <Check size={15} />
                  <span>{item.summary}</span>
                </li>
              ))}
            </ul>
          )}
          {result.pending.length > 0 && (
            <div className="intent-result-pending">
              {result.pending.map((item, index) => (
                <div key={index} className="intent-pending-item">
                  <span className="intent-pending-summary"><Clock size={15} /> {item.summary}</span>
                  {item.tool === "create_story" && (
                    <button
                      className="intent-pending-action"
                      onClick={() => routeStory(String(item.params.theme ?? ""))}
                    >
                      去创作 <ArrowRight size={13} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {showFallback && (
        <div className="intent-fallback">
          {FALLBACK_ENTRIES.map(({ label, desc, href, Icon }) => (
            <button key={label} className="intent-entry" onClick={() => router.push(href)}>
              <Icon size={18} />
              <span><strong>{label}</strong><small>{desc}</small></span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

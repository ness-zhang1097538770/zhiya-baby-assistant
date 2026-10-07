"use client";

import { BookOpenCheck, Copy, Share2, ShieldCheck } from "lucide-react";
import { useState } from "react";
import type { Source } from "@/lib/types";
import { BrandMark } from "@/components/BrandMark";
import { RiskBadge } from "./RiskBadge";
import { ShareCardModal } from "./ShareCardModal";

function isHeading(line: string): boolean {
  return /^【[^】]+】/.test(line);
}

function isRedFlagHeading(line: string): boolean {
  return line.startsWith("【出现这些情况");
}

function AnswerBody({ content }: { content: string }) {
  const lines = content.split("\n");
  return (
    <div className="answer-body">
      {lines.map((line, index) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={index} className="answer-gap" />;
        if (isHeading(trimmed)) {
          return (
            <p key={index} className={isRedFlagHeading(trimmed) ? "answer-heading red" : "answer-heading"}>
              {trimmed}
            </p>
          );
        }
        return <p key={index} className="answer-line">{line}</p>;
      })}
    </div>
  );
}

function SourceList({ sources }: { sources?: Source[] }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="source-list">
      <span className="source-title"><BookOpenCheck size={14} /> 参考来源</span>
      {sources.map((source) => (
        <div key={source.id} className="source-item">
          <strong>{source.title}</strong>
          <span>
            {source.source}
            {source.version ? ` · ${source.version}` : ""}
            {source.review_status ? ` · ${source.review_status}` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}

export function AnswerCard({
  riskLevel,
  content,
  sources,
  followupQuestion,
  question,
  showActions = true,
}: {
  riskLevel?: string | null;
  content: string;
  sources?: Source[];
  followupQuestion?: string | null;
  question?: string | null;
  showActions?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 复制失败时静默
    }
  }

  return (
    <div className="answer-card">
      <div className="answer-meta">
        <span className="ai-logo"><BrandMark size={22} /></span>
        <RiskBadge level={riskLevel} />
        <span className="answer-source-note"><ShieldCheck size={14} /> 循证内容 · 仅供参考</span>
      </div>
      <AnswerBody content={content} />
      {followupQuestion ? <p className="followup-hint">我还想确认：{followupQuestion}</p> : null}
      <SourceList sources={sources} />
      {showActions && content ? (
        <div className="answer-actions">
          <button className="answer-action" onClick={() => void handleCopy()}>
            <Copy size={14} />{copied ? "已复制" : "复制"}
          </button>
          <button className="answer-action" onClick={() => setShareOpen(true)}>
            <Share2 size={14} />分享卡片
          </button>
        </div>
      ) : null}
      <p className="ai-disclaimer">
        <ShieldCheck />
        建议不能替代专业诊疗。孩子出现持续高热、抽搐、呼吸急促、意识不清、拒食脱水等情况，请立即就医或拨打 120。
      </p>
      {shareOpen && <ShareCardModal question={question} content={content} onClose={() => setShareOpen(false)} />}
    </div>
  );
}

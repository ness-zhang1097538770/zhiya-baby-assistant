"use client";

import { X } from "lucide-react";
import { useState } from "react";
import { BrandMark } from "@/components/BrandMark";

export function ShareCardModal({
  question,
  content,
  onClose,
}: {
  question?: string | null;
  content: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copyCard() {
    const text = `【知芽育儿建议】\n\n${question ? `问题：${question}\n\n` : ""}${content}\n\n—— 以上内容仅供参考，不能替代医生诊断。`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 复制失败时静默
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="dialog share-dialog" role="dialog" aria-modal="true" aria-labelledby="share-title" onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <div><span className="eyebrow">分享卡片</span><h2 id="share-title">把建议分享给家人</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="关闭"><X size={20} /></button>
        </div>

        <div className="share-card">
          <div className="share-card-head">
            <span className="share-card-logo"><BrandMark size={30} /></span>
            <span>知芽 · 育儿建议</span>
          </div>
          {question ? <div className="share-card-q">问：{question}</div> : null}
          <div className="share-card-body">{content}</div>
          <div className="share-card-foot">内容仅供参考，不代替医生诊疗</div>
        </div>

        <div className="dialog-actions">
          <button type="button" className="button ghost" onClick={onClose}>关闭</button>
          <button className="button primary" onClick={() => void copyCard()}>{copied ? "已复制" : "复制卡片文案"}</button>
        </div>
        <p className="share-tip">手机上可长按上方卡片截图保存，转发给家人。</p>
      </section>
    </div>
  );
}

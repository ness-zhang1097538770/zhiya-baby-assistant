"use client";

import { X } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { AppError, Child, ChildDraft } from "@/lib/types";

export function ChildDialog({
  child,
  onClose,
  onCreated,
  onUpdated,
}: {
  child?: Child | null;
  onClose: () => void;
  onCreated?: (child: Child) => void;
  onUpdated?: (child: Child) => void;
}) {
  const [nickname, setNickname] = useState(child?.nickname ?? "");
  const [birthDate, setBirthDate] = useState(child?.birth_date ?? "");
  const [gender, setGender] = useState(child?.gender ?? "");
  const [feeding, setFeeding] = useState(child?.feeding_method ?? "");
  const [allergy, setAllergy] = useState(child?.allergy_history ?? "");
  const [premature, setPremature] = useState(child?.premature ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!nickname.trim() || !birthDate) {
      setError("请填写孩子昵称和出生日期。");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const draft: ChildDraft = {
        nickname: nickname.trim(),
        birth_date: birthDate,
        gender: gender || undefined,
        feeding_method: feeding || undefined,
        allergy_history: allergy.trim() || undefined,
        premature: premature.trim() || undefined,
      };
      if (child) {
        const saved = await api.updateChild(child.id, draft);
        onUpdated?.(saved);
      } else {
        const saved = await api.createChild(draft);
        onCreated?.(saved);
      }
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "保存失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="child-dialog-title" onMouseDown={(event) => event.stopPropagation()}>
        <div className="dialog-head">
          <div><span className="eyebrow">成长档案</span><h2 id="child-dialog-title">{child ? "编辑孩子档案" : "添加孩子"}</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="关闭"><X size={20} /></button>
        </div>
        <form onSubmit={submit} className="child-form">
          <label><span>孩子昵称 <b>*</b></span><input value={nickname} onChange={(e) => setNickname(e.target.value)} maxLength={50} placeholder="例如：小糖豆" autoFocus /></label>
          <label><span>出生日期 <b>*</b></span><input type="date" value={birthDate} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setBirthDate(e.target.value)} /></label>
          <div className="form-row">
            <label><span>性别（可选）</span><select value={gender} onChange={(e) => setGender(e.target.value)}><option value="">未选择</option><option>男孩</option><option>女孩</option></select></label>
            <label><span>喂养方式（可选）</span><select value={feeding} onChange={(e) => setFeeding(e.target.value)}><option value="">未选择</option><option>母乳喂养</option><option>配方奶</option><option>混合喂养</option><option>已添加辅食</option></select></label>
          </div>
          <label><span>过敏史（可选）</span><input value={allergy} onChange={(e) => setAllergy(e.target.value)} maxLength={200} placeholder="例如：对鸡蛋过敏" /></label>
          <label><span>是否早产（可选）</span><input value={premature} onChange={(e) => setPremature(e.target.value)} maxLength={50} placeholder="例如：否 / 早产 2 周" /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="dialog-actions"><button type="button" className="button ghost" onClick={onClose}>暂不保存</button><button className="button primary" disabled={saving}>{saving ? "正在保存…" : child ? "保存修改" : "建立成长档案"}</button></div>
        </form>
      </section>
    </div>
  );
}

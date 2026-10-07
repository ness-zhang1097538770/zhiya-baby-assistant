"use client";

import { Camera, X } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import type { AppError, Story, StoryDraft } from "@/lib/types";

const AGE_RANGES = ["0-1岁", "1-2岁", "2-3岁"] as const;
const DURATIONS = [
  { value: "短篇（约5页）", label: "短篇 · 约5页" },
  { value: "中篇（约8页）", label: "中篇 · 约8页" },
  { value: "长篇（约10页）", label: "长篇 · 约10页" },
] as const;

export function StoryCreateDialog({
  childId,
  initialTheme,
  onClose,
  onCreated,
}: {
  childId: number;
  initialTheme?: string;
  onClose: () => void;
  onCreated: (story: Story) => void;
}) {
  const [characterName, setCharacterName] = useState("");
  const [gender, setGender] = useState("女孩");
  const [theme, setTheme] = useState(initialTheme ?? "");
  const [ageRange, setAgeRange] = useState<string>("1-2岁");
  const [duration, setDuration] = useState("");
  const [educationGoal, setEducationGoal] = useState("");
  const [familyMemory, setFamilyMemory] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [characterImage, setCharacterImage] = useState("");
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!characterName.trim() || !theme.trim()) {
      setError("请填写主角名字和故事主题。");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const draft: StoryDraft = {
        character_name: characterName.trim(),
        gender,
        theme: theme.trim(),
        age_range: ageRange,
        duration: duration || undefined,
        education_goal: educationGoal.trim() || undefined,
        family_memory: familyMemory.trim() || undefined,
        character_image: characterImage || undefined,
      };
      const story = await api.createStory(childId, draft);
      onCreated(story);
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "创建失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  }

  async function handlePhotoChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("请选择图片文件。");
      return;
    }
    setUploadingPhoto(true);
    setError("");
    try {
      const result = await api.uploadStoryPhoto(file);
      setCharacterImage(result.character_image);
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "照片处理失败，请稍后重试。");
    } finally {
      setUploadingPhoto(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="story-create-title" onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <div><span className="eyebrow">故事工坊</span><h2 id="story-create-title">创作一本新故事</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="关闭"><X size={20} /></button>
        </div>
        <form onSubmit={submit} className="child-form">
          <label>
            <span>主角名字 <b>*</b></span>
            <input value={characterName} onChange={(e) => setCharacterName(e.target.value)} maxLength={50} placeholder="例如：小糯米" autoFocus />
          </label>
          <div className="form-row">
            <label><span>主角性别</span><select value={gender} onChange={(e) => setGender(e.target.value)}><option>女孩</option><option>男孩</option></select></label>
            <label><span>适合月龄</span><select value={ageRange} onChange={(e) => setAgeRange(e.target.value)}>{AGE_RANGES.map((a) => <option key={a}>{a}</option>)}</select></label>
          </div>
          <label>
            <span>故事主题 <b>*</b></span>
            <input value={theme} onChange={(e) => setTheme(e.target.value)} maxLength={100} placeholder="例如：刷牙、睡觉、分享、去幼儿园" />
          </label>
          <div className="form-row">
            <label><span>篇幅（可选）</span><select value={duration} onChange={(e) => setDuration(e.target.value)}><option value="">默认</option>{DURATIONS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}</select></label>
            <label><span>教育目标（可选）</span><input value={educationGoal} onChange={(e) => setEducationGoal(e.target.value)} maxLength={200} placeholder="例如：爱上刷牙" /></label>
          </div>
          <label>
            <span>家庭记忆（可选）</span>
            <textarea value={familyMemory} onChange={(e) => setFamilyMemory(e.target.value)} rows={2} maxLength={500} placeholder="想写进故事里的小事，例如：宝宝最喜欢小恐龙" />
          </label>
          <div className="photo-upload">
            <span>孩子照片（可选）</span>
            <p className="photo-hint">上传孩子真实照片，AI 生成绘本角色形象（原照片不会保存，只用一次）。</p>
            {characterImage ? (
              <div className="photo-preview">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={characterImage} alt="角色形象预览" />
                <button type="button" className="button ghost" onClick={() => setCharacterImage("")}>移除照片</button>
              </div>
            ) : (
              <button type="button" className="button secondary" onClick={() => fileInputRef.current?.click()} disabled={uploadingPhoto}>
                <Camera size={16} />{uploadingPhoto ? "正在生成角色形象…（约几十秒）" : "上传照片生成角色"}
              </button>
            )}
            <input ref={fileInputRef} type="file" accept="image/*" hidden onChange={handlePhotoChange} />
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="dialog-actions">
            <button type="button" className="button ghost" onClick={onClose}>取消</button>
            <button className="button primary" disabled={saving}>{saving ? "正在创建…" : "开始创作"}</button>
          </div>
        </form>
      </section>
    </div>
  );
}

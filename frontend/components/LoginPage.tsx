"use client";

import { useState } from "react";
import { BrandMark } from "@/components/BrandMark";
import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";
import type { AppError } from "@/lib/types";

export function LoginPage({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!code.trim()) {
      setError("请输入邀请码。");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await api.login(code.trim());
      setToken(result.token);
      onLoggedIn();
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "登录失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <span className="login-mark"><BrandMark size={52} /></span>
        <span className="eyebrow">知芽</span>
        <h1>欢迎回来</h1>
        <p>输入邀请码，进入你的育儿小天地</p>
        <form onSubmit={submit} className="login-form">
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="邀请码"
            maxLength={20}
            autoFocus
            autoComplete="off"
            aria-label="邀请码"
          />
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button primary large" disabled={loading}>{loading ? "正在进入…" : "进入知芽"}</button>
        </form>
        <p className="login-note">内部试用版 · 邀请码由管理员发放</p>
      </div>
    </div>
  );
}

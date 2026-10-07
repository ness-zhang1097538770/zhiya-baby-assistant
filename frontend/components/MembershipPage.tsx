"use client";

import {
  BookHeart,
  Check,
  Crown,
  LoaderCircle,
  RefreshCw,
  Sparkles,
  Ticket,
  Users,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AppError, Entitlements } from "@/lib/types";

const PLAN_LABEL: Record<string, string> = {
  free: "免费版",
  monthly: "连续包月",
  yearly: "年卡会员",
  trial: "试用",
};

const SUBSCRIPTIONS = [
  { source: "promo_99", label: "内测首年尝鲜", price: "¥99", period: "首年", note: "限时 / 限量，验证期专属" },
  { source: "yearly_198", label: "年卡（主推）", price: "¥198", period: "年", note: "折合月均 ¥16.5" },
  { source: "monthly_28", label: "连续包月", price: "¥28", period: "月", note: "自动续费，可随时取消" },
];

const PURCHASES = [
  { sku: "pack_5", label: "绘本包 · 小", price: "¥9.9", desc: "5 本 · 30 天有效" },
  { sku: "pack_20", label: "绘本包 · 大", price: "¥29.9", desc: "20 本 · 90 天有效" },
];

const BENEFITS: { label: string; free: string; member: string }[] = [
  { label: "育儿问答", free: "每日 30 次", member: "每日 100 次 + 长答案" },
  { label: "数字绘本", free: "新赠 3 本，此后 1 本/月", member: "每月 30 本" },
  { label: "AI 成长洞察", free: "当月基础统计", member: "AI 周报 + 月报 + 趋势" },
  { label: "家庭协作", free: "1 个孩子", member: "多儿童 + 家人共享" },
  { label: "书架与导出", free: "保留最近 20 本", member: "无限书架 + PDF 导出" },
  { label: "记忆读回", free: "近 3 个月", member: "全量事实" },
  { label: "广告", free: "克制展示", member: "全站无广告" },
];

export function MembershipPage() {
  const [phase, setPhase] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);
  const [redeemCode, setRedeemCode] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setPhase("loading");
    setError("");
    try {
      setEntitlements(await api.getEntitlements());
      setPhase("ready");
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "会员信息暂时加载失败。");
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function doSubscribe(source: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.subscribe(source);
      setNotice("已开通，感谢支持！");
      await load();
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "开通失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }

  async function doRedeem() {
    const code = redeemCode.trim();
    if (!code) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.redeem(code);
      setNotice("兑换成功！");
      setRedeemCode("");
      await load();
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "兑换失败，请检查兑换码。");
    } finally {
      setBusy(false);
    }
  }

  async function doPurchase(sku: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.purchase(sku);
      setNotice("已加购，额度即时到账。");
      await load();
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "加购失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }

  async function doCancelRenew() {
    if (!window.confirm("确定取消自动续费吗？当前周期内仍可继续使用会员权益。")) return;
    setBusy(true);
    try {
      await api.cancelRenew();
      setNotice("已取消自动续费。");
      await load();
    } catch (caught) {
      setError((caught as AppError).userMessage ?? "操作失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }

  if (phase === "loading") {
    return <div className="page-state" role="status"><LoaderCircle className="spin" size={30} /><strong>正在读取会员信息…</strong></div>;
  }

  if (phase === "error" || !entitlements) {
    return <div className="page-state error-state"><X size={30} /><strong>暂时没能连上服务</strong><span>{error}</span><button className="button secondary" onClick={() => void load()}><RefreshCw size={17} />重新连接</button></div>;
  }

  const member = entitlements.plan !== "free";

  return (
    <div className="membership-page">
      <header className="topbar">
        <div><p className="kicker">会员</p><h1>知芽会员与绘本额度</h1></div>
      </header>

      {notice ? <p className="membership-notice" role="status"><Check size={15} />{notice}</p> : null}
      {error ? <p className="form-error" role="alert">{error}</p> : null}

      {/* 当前状态 */}
      <section className="membership-hero">
        <div className="membership-hero-copy">
          <span className="eyebrow">当前方案</span>
          <h2>{PLAN_LABEL[entitlements.plan] ?? entitlements.plan}</h2>
          <p className="membership-muted">
            {member
              ? `有效期至 ${entitlements.period_end?.slice(0, 10) ?? "—"}${entitlements.auto_renew ? " · 自动续费中" : ""}`
              : "免费版 · 完整养大 1 个孩子"}
          </p>
        </div>
        <div className="membership-quota">
          <BookHeart size={22} />
          <div><strong>{entitlements.story_books_available}</strong><small>本月剩余绘本（本）</small></div>
        </div>
        {member && entitlements.auto_renew ? (
          <button className="button ghost" onClick={() => void doCancelRenew()} disabled={busy}>取消自动续费</button>
        ) : null}
      </section>

      {/* 订阅 */}
      <section className="profile-section">
        <div className="profile-section-head"><span className="profile-icon"><Crown size={18} /></span><div><span className="eyebrow">会员订阅</span><h2>升级会员</h2></div></div>
        <p className="membership-muted">内测期走白名单开通，不真实扣款；正式支付接入后价格以购买页为准。</p>
        <div className="plan-grid">
          {SUBSCRIPTIONS.map((s) => (
            <button key={s.source} className="plan-card" disabled={busy} onClick={() => void doSubscribe(s.source)}>
              <strong>{s.label}</strong>
              <span className="plan-price">{s.price}<small>/{s.period}</small></span>
              <span className="plan-note">{s.note}</span>
              <span className="button primary plan-button">开通</span>
            </button>
          ))}
        </div>
      </section>

      {/* 兑换码 */}
      <section className="profile-section">
        <div className="profile-section-head"><span className="profile-icon"><Ticket size={18} /></span><div><span className="eyebrow">兑换码</span><h2>用邀请码开通</h2></div></div>
        <div className="membership-redeem">
          <input value={redeemCode} onChange={(e) => setRedeemCode(e.target.value)} placeholder="输入兑换码" maxLength={32} aria-label="兑换码" />
          <button className="button secondary" onClick={() => void doRedeem()} disabled={busy || !redeemCode.trim()}>兑换</button>
        </div>
      </section>

      {/* 加购 */}
      <section className="profile-section">
        <div className="profile-section-head"><span className="profile-icon"><Sparkles size={18} /></span><div><span className="eyebrow">单次加购</span><h2>绘本额度不够用？</h2></div></div>
        <div className="plan-grid">
          {PURCHASES.map((p) => (
            <button key={p.sku} className="plan-card" disabled={busy} onClick={() => void doPurchase(p.sku)}>
              <strong>{p.label}</strong>
              <span className="plan-price">{p.price}</span>
              <span className="plan-note">{p.desc}</span>
              <span className="button secondary plan-button">加购</span>
            </button>
          ))}
        </div>
      </section>

      {/* 权益对照 */}
      <section className="profile-section">
        <div className="profile-section-head"><span className="profile-icon"><Users size={18} /></span><div><span className="eyebrow">权益对照</span><h2>免费版 vs 会员版</h2></div></div>
        <table className="benefit-table">
          <thead><tr><th>能力</th><th>免费版</th><th>会员版</th></tr></thead>
          <tbody>
            {BENEFITS.map((b) => (
              <tr key={b.label}>
                <td>{b.label}</td>
                <td>{b.free}</td>
                <td className="benefit-member">{b.member}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

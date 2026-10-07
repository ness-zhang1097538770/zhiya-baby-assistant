"use client";

import { useEffect, useState } from "react";
import { fetchAds, logAdEvent, shouldShowAd, type AdItem } from "@/lib/ads";

/**
 * 广告位组件（C-2 框架，不上真实投放）。
 * 硬屏蔽：风险回答页(L1/L2/L3)、医疗会话、会员 均不渲染；广告目录为空时渲染 null。
 */
export function AdSlot({
  page,
  ageBucket,
  consent,
  riskLevel,
  medical,
  isMember,
}: {
  page: string;
  ageBucket: string;
  consent: boolean;
  riskLevel?: string | null;
  medical?: boolean;
  isMember?: boolean;
}) {
  const [ads, setAds] = useState<AdItem[]>([]);

  const blocked = !shouldShowAd({ riskLevel, medical, isMember });

  useEffect(() => {
    if (blocked || !consent) return;
    let cancelled = false;
    fetchAds({ page, ageBucket, consent, riskLevel, medical }).then((items) => {
      if (cancelled) return;
      setAds(items);
      if (items.length > 0) {
        logAdEvent({ slot: page, ageBucket, action: "impression", adId: items[0].ad_id });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [page, ageBucket, consent, riskLevel, medical, blocked]);

  if (blocked || ads.length === 0) return null;

  const ad = ads[0];
  return (
    <div className="my-2 flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600">
      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-400">广告</span>
      <span className="flex-1 truncate">{ad.title || ad.advertiser}</span>
      <button
        type="button"
        aria-label="关闭广告"
        className="text-slate-400 hover:text-slate-600"
        onClick={() => logAdEvent({ slot: page, ageBucket, action: "close", adId: ad.ad_id })}
      >
        ✕
      </button>
    </div>
  );
}

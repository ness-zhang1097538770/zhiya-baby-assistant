"use client";

import { AlertTriangle, CheckCircle, Eye, Info } from "lucide-react";
import { riskLabel, riskTone } from "@/lib/format";

/** 每个风险等级都配图标，不依赖颜色单通道区分（色盲友好） */
const RISK_ICONS: Record<string, typeof Info> = {
  "risk-l1": AlertTriangle,
  "risk-l2": AlertTriangle,
  "risk-l3": Eye,
  "risk-l4": CheckCircle,
  "risk-info": Info,
};

export function RiskBadge({ level }: { level?: string | null }) {
  const tone = riskTone(level);
  const Icon = RISK_ICONS[tone] ?? Info;
  return (
    <span className={`risk-badge ${tone}`}>
      <Icon strokeWidth={2.4} />
      {riskLabel(level)}
    </span>
  );
}

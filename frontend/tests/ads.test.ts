import { describe, expect, it } from "vitest";
import { shouldShowAd } from "../lib/ads";

describe("广告硬屏蔽规则（前端）", () => {
  it("风险回答页 L1/L2/L3 不展示广告", () => {
    expect(shouldShowAd({ riskLevel: "L1" })).toBe(false);
    expect(shouldShowAd({ riskLevel: "L2" })).toBe(false);
    expect(shouldShowAd({ riskLevel: "L3" })).toBe(false);
  });

  it("L4 与空风险等级不屏蔽", () => {
    expect(shouldShowAd({ riskLevel: "L4" })).toBe(true);
    expect(shouldShowAd({ riskLevel: null })).toBe(true);
    expect(shouldShowAd({})).toBe(true);
  });

  it("医疗会话不展示广告", () => {
    expect(shouldShowAd({ medical: true })).toBe(false);
    expect(shouldShowAd({ medical: false })).toBe(true);
  });

  it("会员全站无广告", () => {
    expect(shouldShowAd({ isMember: true })).toBe(false);
    expect(shouldShowAd({ isMember: false })).toBe(true);
  });

  it("多条件叠加：任一命中即屏蔽", () => {
    expect(shouldShowAd({ riskLevel: "L4", medical: true })).toBe(false);
    expect(shouldShowAd({ riskLevel: "L4", isMember: true })).toBe(false);
  });
});

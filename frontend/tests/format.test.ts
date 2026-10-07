import { describe, expect, it } from "vitest";
import { ageLabel, dateLabel, eventDetail, eventLabel, isStoryRunning, reminderLabel, riskLabel, riskTone, storyCover, storyStatusLabel, toApiDatetime } from "../lib/format";

describe("dashboard formatting", () => {
  it("formats months and years without overcounting", () => {
    const now = new Date("2026-09-16T12:00:00");
    expect(ageLabel("2026-01-20", now)).toBe("7 个月");
    expect(ageLabel("2024-09-16", now)).toBe("2 岁");
  });

  it("uses safe fallback labels", () => {
    expect(eventLabel("sleep")).toBe("睡眠");
    expect(eventLabel("unknown")).toBe("成长记录");
  });

  it("reads story covers from supported backend shapes", () => {
    expect(storyCover(["/story_assets/1/page_1.png"])).toBe("/story_assets/1/page_1.png");
    expect(storyCover([{ path: "/story_assets/2/page_1.png" }])).toBe("/story_assets/2/page_1.png");
    expect(storyCover(null)).toBeNull();
  });

  it("maps risk levels to labels and tones", () => {
    expect(riskLabel("L1")).toBe("危急");
    expect(riskLabel("L2")).toBe("紧急");
    expect(riskLabel("L4")).toBe("常规");
    expect(riskLabel("NEED_MORE_INFO")).toBe("需要补充信息");
    expect(riskLabel(undefined)).toBe("育儿建议");
    expect(riskTone("L1")).toBe("risk-l1");
    expect(riskTone("L4")).toBe("risk-l4");
    expect(riskTone(null)).toBe("risk-info");
  });

  it("maps reminder types to labels", () => {
    expect(reminderLabel("vaccine")).toBe("疫苗");
    expect(reminderLabel("routine")).toBe("作息");
    expect(reminderLabel("unknown")).toBe("提醒");
  });

  it("renders event detail from structured data", () => {
    expect(eventDetail("feeding", { amount: "120ml" }, null)).toBe("120ml");
    expect(eventDetail("sleep", { duration: "2 小时" }, null)).toBe("2 小时");
    expect(eventDetail("growth", { height: "72.5", weight: "9.2" }, null)).toBe("身高 72.5 cm · 体重 9.2 kg");
    expect(eventDetail("milestone", null, "第一次翻身")).toBe("第一次翻身");
    expect(eventDetail("feeding", null, null)).toBe("喂养记录");
  });

  it("labels timeline dates as today/yesterday/date", () => {
    const now = new Date("2026-09-16T12:00:00");
    expect(dateLabel("2026-09-16", now)).toBe("今天");
    expect(dateLabel("2026-09-15", now)).toBe("昨天");
    expect(dateLabel("2026-09-14", now)).toContain("9月");
  });

  it("pads datetime-local values to API datetime", () => {
    expect(toApiDatetime("2026-09-16T08:30")).toBe("2026-09-16T08:30:00");
    expect(toApiDatetime("2026-09-16T08:30:00")).toBe("2026-09-16T08:30:00");
    expect(toApiDatetime("")).toBe("");
  });

  it("maps story statuses to labels and running states", () => {
    expect(storyStatusLabel("outline_ready")).toBe("待确认大纲");
    expect(storyStatusLabel("ready")).toBe("已完成");
    expect(storyStatusLabel("failed")).toBe("生成失败");
    expect(isStoryRunning("assets_generating")).toBe(true);
    expect(isStoryRunning("ready")).toBe(false);
  });
});

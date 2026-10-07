import { describe, expect, it } from "vitest";
import { reminderNotificationDecision } from "../lib/notifications";

const now = new Date("2026-09-18T12:00:00");

describe("reminderNotificationDecision", () => {
  it("schedules an enabled future reminder", () => {
    const decision = reminderNotificationDecision({ enabled: true, remind_at: "2026-09-18T13:00:00" }, now);
    expect(decision.schedule).toBe(true);
    expect(decision.at.getTime()).toBe(new Date("2026-09-18T13:00:00").getTime());
  });

  it("does not schedule a disabled reminder", () => {
    expect(reminderNotificationDecision({ enabled: false, remind_at: "2026-09-18T13:00:00" }, now).schedule).toBe(false);
  });

  it("does not schedule a past reminder", () => {
    expect(reminderNotificationDecision({ enabled: true, remind_at: "2026-09-18T11:00:00" }, now).schedule).toBe(false);
  });

  it("does not schedule an invalid date", () => {
    expect(reminderNotificationDecision({ enabled: true, remind_at: "not-a-date" }, now).schedule).toBe(false);
  });
});

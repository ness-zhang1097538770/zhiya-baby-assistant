import { describe, expect, it } from "vitest";
import { buildEventPayload } from "../lib/analytics";

describe("产品行为埋点载荷", () => {
  it("组装 device_id + event + props", () => {
    const p = buildEventPayload("qa_ask", { risk_level: "L4" });
    expect(p.event).toBe("qa_ask");
    expect(typeof p.device_id).toBe("string");
    expect(p.props).toEqual({ risk_level: "L4" });
  });

  it("无 props 时置 null", () => {
    const p = buildEventPayload("story_created");
    expect(p.props).toBeNull();
  });
});

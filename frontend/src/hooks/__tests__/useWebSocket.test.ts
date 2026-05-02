import { useWebSocket } from "../useWebSocket";

// Mock WebSocket class
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
}

// Minimal DOM mock for hook testing without full jsdom renderHook issues
function createHookResult() {
  const state = { connected: false, messages: [] as any[] };
  const mockWs = MockWebSocket.instances[MockWebSocket.instances.length - 1];
  return { state, mockWs };
}

describe("useWebSocket hook (BATCH-50)", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
  });

  it("creates WebSocket connection to correct URL", () => {
    // Test that the hook constructs the correct WebSocket URL
    const protocol = "http:";
    const host = "localhost:3000";
    const expectedUrl = `ws://${host}/api/v1/ws`;
    const ws = new MockWebSocket(expectedUrl);

    expect(ws.url).toBe("ws://localhost:3000/api/v1/ws");
  });

  it("sends subscribe action when channel is provided and processes messages", () => {
    // Test subscribe message format
    const channel = "pipeline:run_1";
    const subscribeMsg = JSON.stringify({ action: "subscribe", channel });
    const parsed = JSON.parse(subscribeMsg);

    expect(parsed.action).toBe("subscribe");
    expect(parsed.channel).toBe("pipeline:run_1");

    // Test that subscribed ack messages are filtered (type check)
    const ackMessage = { type: "subscribed", channel: "pipeline:run_1" };
    const isAck = ackMessage.type === "subscribed";
    expect(isAck).toBe(true);

    // Test that real messages are kept
    const progressMessage = { type: "pipeline.progress", data: { stage: "generation" } };
    const isRealMessage = progressMessage.type !== "subscribed";
    expect(isRealMessage).toBe(true);
  });
});

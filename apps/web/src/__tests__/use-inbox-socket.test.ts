import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useInboxSocket } from "@/lib/ws/use-inbox-socket";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

class FakeWebSocket {
  static OPEN = 1;
  static instances: FakeWebSocket[] = [];

  url: string;
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  receive(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}

describe("useInboxSocket", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("exchanges a ticket and opens a websocket with it", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ ticket: "tok-1" }));
    const onEvent = vi.fn();

    renderHook(() => useInboxSocket(onEvent));

    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    expect(fetch).toHaveBeenCalledWith("/api/proxy/auth/ws-ticket", { method: "POST" });
    expect(FakeWebSocket.instances[0].url).toContain("ticket=tok-1");
  });

  it("dispatches parsed events from the socket to the callback", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ ticket: "tok-2" }));
    const onEvent = vi.fn();

    renderHook(() => useInboxSocket(onEvent));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    const ws = FakeWebSocket.instances[0];

    act(() => {
      ws.open();
      ws.receive({ type: "handoff.created", conversation_id: "c1", reason: "low_confidence", rag_score: 0.4 });
    });

    expect(onEvent).toHaveBeenCalledWith({
      type: "handoff.created",
      conversation_id: "c1",
      reason: "low_confidence",
      rag_score: 0.4,
    });
  });

  it("ignores malformed frames instead of throwing", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ ticket: "tok-3" }));
    const onEvent = vi.fn();

    renderHook(() => useInboxSocket(onEvent));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    const ws = FakeWebSocket.instances[0];

    expect(() => ws.onmessage?.({ data: "not json" })).not.toThrow();
    expect(onEvent).not.toHaveBeenCalled();
  });

  it("sendPresence only sends once the socket is open", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ ticket: "tok-4" }));
    const onEvent = vi.fn();

    const { result } = renderHook(() => useInboxSocket(onEvent));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    const ws = FakeWebSocket.instances[0];

    act(() => result.current.sendPresence("c1", true));
    expect(ws.sent).toHaveLength(0); // socket not open yet

    act(() => ws.open());
    act(() => result.current.sendPresence("c1", true));
    expect(JSON.parse(ws.sent[0])).toEqual({ type: "presence.join", conversation_id: "c1" });

    act(() => result.current.sendPresence("c1", false));
    expect(JSON.parse(ws.sent[1])).toEqual({ type: "presence.leave", conversation_id: "c1" });
  });

  it("reconnects with a fresh ticket after the socket closes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ ticket: "tok-5" }))
      .mockResolvedValueOnce(jsonResponse({ ticket: "tok-6" }));
    const onEvent = vi.fn();

    renderHook(() => useInboxSocket(onEvent));
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));

    act(() => FakeWebSocket.instances[0].close());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[1].url).toContain("ticket=tok-6");
    vi.useRealTimers();
  });
});

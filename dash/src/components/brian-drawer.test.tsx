import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: pushMock }),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
  Toaster: () => null,
}));

import { BrianDrawer } from "./brian-drawer";

const OPEN_EVENT = "brian:open";

function sseStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(ctrl) {
      for (const c of chunks) ctrl.enqueue(encoder.encode(c));
      ctrl.close();
    },
  });
}

describe("BrianDrawer", () => {
  beforeEach(() => {
    pushMock.mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders closed by default — nothing visible", () => {
    render(<BrianDrawer />);
    expect(screen.queryByText(/Brian the Brain/i)).toBeNull();
  });

  it("opens on custom brian:open event and shows empty state", () => {
    render(<BrianDrawer />);
    act(() => {
      window.dispatchEvent(new CustomEvent(OPEN_EVENT));
    });
    expect(screen.getByText(/Brian the Brain/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Ask Brian anything/i),
    ).toBeInTheDocument();
  });

  it("redirects to /login when no API key is in localStorage", async () => {
    render(<BrianDrawer />);
    act(() => {
      window.dispatchEvent(new CustomEvent(OPEN_EVENT));
    });

    const user = userEvent.setup();
    const textarea = screen.getByPlaceholderText(/Message Brian/i);
    await user.type(textarea, "hello");
    await user.click(screen.getByLabelText(/Send message/i));

    expect(pushMock).toHaveBeenCalledWith("/login");
  });

  it("streams tokens from SSE and appends them to the assistant bubble", async () => {
    window.localStorage.setItem("occp_api_key", "occp_live_sk_test");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: sseStream([
        'data: {"token":"Hello"}\n\n',
        'data: {"token":", world"}\n\n',
        "data: [DONE]\n\n",
      ]),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BrianDrawer />);
    act(() => {
      window.dispatchEvent(new CustomEvent(OPEN_EVENT));
    });

    const user = userEvent.setup();
    const textarea = screen.getByPlaceholderText(/Message Brian/i);
    await user.type(textarea, "hi");
    await user.click(screen.getByLabelText(/Send message/i));

    await vi.waitFor(() => {
      expect(screen.getByText(/Hello, world/)).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toMatch(/^Bearer occp_live_sk_/);
    expect(init.headers.Accept).toBe("text/event-stream");
    expect(init.headers["X-OCCP-Cache-Control"]).toBe("ttl=3600");
    const body = JSON.parse(init.body);
    expect(body.message).toBe("hi");
    expect(body.session_id).toMatch(/^sess_/);
  });

  it("redirects to /login on 401 response", async () => {
    window.localStorage.setItem("occp_api_key", "occp_live_sk_test");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      body: null,
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BrianDrawer />);
    act(() => {
      window.dispatchEvent(new CustomEvent(OPEN_EVENT));
    });

    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/Message Brian/i), "hi");
    await user.click(screen.getByLabelText(/Send message/i));

    await vi.waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/login");
    });
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Stub next/server with minimal, inspectable implementations so we can
// assert on the middleware's behavior without booting the Edge runtime.
vi.mock("next/server", () => {
  type ResponseKind = "redirect" | "rewrite" | "next";
  class FakeNextResponse {
    constructor(
      public kind: ResponseKind,
      public url?: URL,
      public status?: number,
    ) {}
    static redirect(url: URL, status = 307): FakeNextResponse {
      return new FakeNextResponse("redirect", url, status);
    }
    static rewrite(url: URL): FakeNextResponse {
      return new FakeNextResponse("rewrite", url);
    }
    static next(): FakeNextResponse {
      return new FakeNextResponse("next");
    }
  }
  return { NextResponse: FakeNextResponse };
});

import { middleware } from "./middleware";

type MockReq = {
  nextUrl: { pathname: string };
  url: string;
};

const makeReq = (pathname: string): MockReq => ({
  nextUrl: { pathname },
  url: `http://localhost:3000${pathname}`,
});

const ORIGINAL_FLAG = process.env.NEXT_PUBLIC_DASH_V2;

describe("middleware: NEXT_PUBLIC_DASH_V2 routing", () => {
  beforeEach(() => {
    delete process.env.NEXT_PUBLIC_DASH_V2;
  });

  afterEach(() => {
    if (ORIGINAL_FLAG === undefined) {
      delete process.env.NEXT_PUBLIC_DASH_V2;
    } else {
      process.env.NEXT_PUBLIC_DASH_V2 = ORIGINAL_FLAG;
    }
  });

  it("flag ON + /pipeline -> 302 redirect to /v2/pipeline", () => {
    process.env.NEXT_PUBLIC_DASH_V2 = "true";
    const res = middleware(makeReq("/pipeline") as never) as unknown as {
      kind: string;
      url: URL;
      status: number;
    };
    expect(res.kind).toBe("redirect");
    expect(res.status).toBe(302);
    expect(res.url.pathname).toBe("/v2/pipeline");
  });

  it("flag ON + each legacy path -> redirect to /v2/<path>", () => {
    process.env.NEXT_PUBLIC_DASH_V2 = "true";
    for (const p of ["/agents", "/audit", "/mcp", "/settings", "/admin"]) {
      const res = middleware(makeReq(p) as never) as unknown as {
        kind: string;
        url: URL;
      };
      expect(res.kind).toBe("redirect");
      expect(res.url.pathname).toBe(`/v2${p}`);
    }
  });

  it("flag OFF + /pipeline -> NextResponse.next() (pass through)", () => {
    // flag intentionally unset
    const res = middleware(makeReq("/pipeline") as never) as unknown as {
      kind: string;
    };
    expect(res.kind).toBe("next");
  });

  it("flag ON + /v2/pipeline -> pass through (no redirect loop)", () => {
    process.env.NEXT_PUBLIC_DASH_V2 = "true";
    const res = middleware(makeReq("/v2/pipeline") as never) as unknown as {
      kind: string;
    };
    expect(res.kind).toBe("next");
  });

  it("flag OFF + /v2/pipeline -> rewrite to /404", () => {
    process.env.NEXT_PUBLIC_DASH_V2 = "false";
    const res = middleware(makeReq("/v2/pipeline") as never) as unknown as {
      kind: string;
      url: URL;
    };
    expect(res.kind).toBe("rewrite");
    expect(res.url.pathname).toBe("/404");
  });

  it("flag unset (undefined) + /v2/admin -> rewrite to /404", () => {
    const res = middleware(makeReq("/v2/admin") as never) as unknown as {
      kind: string;
      url: URL;
    };
    expect(res.kind).toBe("rewrite");
    expect(res.url.pathname).toBe("/404");
  });
});

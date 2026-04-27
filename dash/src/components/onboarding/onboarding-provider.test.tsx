import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, render, renderHook } from "@testing-library/react";
import {
  OnboardingProvider,
  useTour,
  readHintsGloballyEnabled,
} from "./onboarding-provider";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <OnboardingProvider autoStart={false}>{children}</OnboardingProvider>
);

describe("OnboardingProvider", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.useFakeTimers();
  });

  it("starts in idle when no persisted state and autoStart=false", () => {
    const { result } = renderHook(() => useTour(), { wrapper });
    expect(result.current.state).toBe("idle");
  });

  it("auto-starts after delay when no tour_state and autoStart=true", () => {
    function Wrap({ children }: { children: React.ReactNode }) {
      return (
        <OnboardingProvider autoStart autoStartDelayMs={500}>
          {children}
        </OnboardingProvider>
      );
    }
    const { result } = renderHook(() => useTour(), { wrapper: Wrap });
    expect(result.current.state).toBe("idle");
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(result.current.state).toBe("step-1");
  });

  it("restores 'completed' from localStorage on mount", () => {
    window.localStorage.setItem("occp_tour_state_v1", "completed");
    const { result } = renderHook(() => useTour(), { wrapper });
    expect(result.current.state).toBe("idle");
  });

  it("skipTour writes dismissed and stays in idle on next mount", () => {
    const { result, unmount } = renderHook(() => useTour(), { wrapper });
    act(() => {
      result.current.startTour();
    });
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(result.current.state).toBe("step-1");
    act(() => {
      result.current.skipTour();
    });
    expect(result.current.state).toBe("dismissed");
    expect(window.localStorage.getItem("occp_tour_state_v1")).toBe("dismissed");
    unmount();
    const { result: r2 } = renderHook(() => useTour(), { wrapper });
    expect(r2.current.state).toBe("idle");
  });

  it("nextStep advances through 5 steps then to completed", () => {
    const { result } = renderHook(() => useTour(), { wrapper });
    act(() => {
      result.current.startTour();
    });
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(result.current.state).toBe("step-1");
    for (const expected of ["step-2", "step-3", "step-4", "step-5", "completed"] as const) {
      act(() => {
        result.current.nextStep();
      });
      expect(result.current.state).toBe(expected);
    }
    expect(window.localStorage.getItem("occp_tour_state_v1")).toBe("completed");
  });

  it("prevStep goes back without writing localStorage", () => {
    const { result } = renderHook(() => useTour(), { wrapper });
    act(() => {
      result.current.startTour();
    });
    act(() => {
      vi.advanceTimersByTime(50);
    });
    act(() => {
      result.current.nextStep();
      result.current.nextStep();
    });
    expect(result.current.state).toBe("step-3");
    act(() => {
      result.current.prevStep();
    });
    expect(result.current.state).toBe("step-2");
    expect(window.localStorage.getItem("occp_tour_state_v1")).toBeNull();
  });

  it("setPersona persists to localStorage", () => {
    const { result } = renderHook(() => useTour(), { wrapper });
    act(() => {
      result.current.setPersona("compliance");
    });
    expect(result.current.persona).toBe("compliance");
    expect(window.localStorage.getItem("occp_tour_persona")).toBe("compliance");
  });

  it("resetAllHints removes occp_hint_* keys and re-enables hints", () => {
    window.localStorage.setItem("occp_hint_cmdk_v1", "dismissed");
    window.localStorage.setItem("occp_hint_brian_v1", "dismissed");
    window.localStorage.setItem("occp_all_hints_dismissed", "true");
    window.localStorage.setItem("occp_hints_enabled", "false");
    const { result } = renderHook(() => useTour(), { wrapper });
    act(() => {
      result.current.resetAllHints();
    });
    expect(window.localStorage.getItem("occp_hint_cmdk_v1")).toBeNull();
    expect(window.localStorage.getItem("occp_hint_brian_v1")).toBeNull();
    expect(window.localStorage.getItem("occp_all_hints_dismissed")).toBeNull();
    expect(window.localStorage.getItem("occp_hints_enabled")).toBe("true");
    expect(readHintsGloballyEnabled()).toBe(true);
  });

  it("restartTour clears state and triggers starting → step-1", () => {
    window.localStorage.setItem("occp_tour_state_v1", "completed");
    const { result } = renderHook(() => useTour(), { wrapper });
    act(() => {
      result.current.restartTour();
    });
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(result.current.state).toBe("step-1");
    expect(window.localStorage.getItem("occp_tour_state_v1")).toBeNull();
  });

  it("readHintsGloballyEnabled returns false when occp_hints_enabled='false'", () => {
    window.localStorage.setItem("occp_hints_enabled", "false");
    expect(readHintsGloballyEnabled()).toBe(false);
    window.localStorage.removeItem("occp_hints_enabled");
    expect(readHintsGloballyEnabled()).toBe(true);
  });

  it("throws clear error when useTour called outside provider", () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<NoProviderConsumer />)).toThrow(/OnboardingProvider/);
    errSpy.mockRestore();
  });
});

function NoProviderConsumer() {
  useTour();
  return null;
}

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  StatusPill,
  STATUS_PILL_VARIANTS,
  type StatusPillVariant,
} from "./status-pill";

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

describe("StatusPill", () => {
  // 7 cases — one per variant
  for (const variant of STATUS_PILL_VARIANTS) {
    it(`renders the "${variant}" variant with role, label, and icon`, () => {
      render(<StatusPill variant={variant as StatusPillVariant} />);
      const pill = screen.getByRole("status");
      const expectedLabel = capitalize(variant);

      expect(pill).toBeInTheDocument();
      expect(pill).toHaveAttribute("aria-label", expectedLabel);
      expect(pill).toHaveAttribute("data-variant", variant);
      expect(pill).toHaveTextContent(expectedLabel);
      // Icon present in default (non-compact) mode
      expect(pill.querySelector('[data-testid="status-pill-icon"]')).not.toBeNull();
    });
  }

  it("compact prop reduces padding and hides the icon", () => {
    render(<StatusPill variant="passed" compact />);
    const pill = screen.getByRole("status");

    // Padding class assertion
    expect(pill.className).toMatch(/px-1\.5/);
    expect(pill.className).toMatch(/py-0(?!\.)/);
    expect(pill.className).not.toMatch(/px-2(?!\.)/);

    // Icon hidden in compact
    expect(pill.querySelector('[data-testid="status-pill-icon"]')).toBeNull();
  });

  it("custom label overrides the auto-derived variant name", () => {
    render(<StatusPill variant="running" label="In flight" />);
    const pill = screen.getByRole("status");
    expect(pill).toHaveAttribute("aria-label", "In flight");
    expect(pill).toHaveTextContent("In flight");
    expect(pill).not.toHaveTextContent("Running");
  });
});

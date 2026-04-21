import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { Hero } from "./hero";

describe("Hero", () => {
  it("renders the audit-first H1", () => {
    render(<Hero />);
    // headline is split across nodes — match the stable prefix
    expect(screen.getByText(/Ship AI agents you can/)).toBeInTheDocument();
    expect(screen.getByText(/defend in an audit/i)).toBeInTheDocument();
  });

  it("exposes both primary and secondary CTAs", () => {
    render(<Hero />);
    const start = screen.getByRole("link", { name: /start free/i });
    const docs = screen.getByRole("link", { name: /read the docs/i });
    expect(start).toHaveAttribute(
      "href",
      "https://dash.occp.ai/onboarding/start",
    );
    expect(docs).toHaveAttribute("href", "https://docs.occp.ai");
  });

  it("shows the v1.0 compliance badge", () => {
    render(<Hero />);
    expect(screen.getByText(/v1\.0/i)).toBeInTheDocument();
    expect(screen.getByText(/EU AI Act Art\. 14/i)).toBeInTheDocument();
  });

  it("defaults to the Python code snippet", () => {
    render(<Hero />);
    expect(screen.getByTestId("snippet-python")).toHaveTextContent(
      "pip install occp",
    );
  });
});

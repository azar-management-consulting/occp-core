import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { NextIntlClientProvider } from "next-intl";
import { Hero } from "./hero";
import en from "../../../messages/en.json";

function renderWithI18n(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      {ui}
    </NextIntlClientProvider>,
  );
}

describe("Hero", () => {
  it("renders the audit-first H1", () => {
    renderWithI18n(<Hero />);
    expect(screen.getByText(/Ship AI agents you can/)).toBeInTheDocument();
    expect(screen.getByText(/defend in an audit/i)).toBeInTheDocument();
  });

  it("exposes both primary and secondary CTAs", () => {
    renderWithI18n(<Hero />);
    const start = screen.getByRole("link", { name: /start free/i });
    const docs = screen.getByRole("link", { name: /read the docs/i });
    expect(start).toHaveAttribute(
      "href",
      "https://dash.occp.ai/onboarding/start",
    );
    expect(docs).toHaveAttribute("href", "https://docs.occp.ai");
  });

  it("shows the v1.0 compliance badge", () => {
    renderWithI18n(<Hero />);
    expect(screen.getByText(/v1\.0/i)).toBeInTheDocument();
    expect(screen.getByText(/EU AI Act Art\. 14/i)).toBeInTheDocument();
  });

  it("defaults to the Python code snippet", () => {
    renderWithI18n(<Hero />);
    expect(screen.getByTestId("snippet-python")).toHaveTextContent(
      "pip install occp",
    );
  });
});

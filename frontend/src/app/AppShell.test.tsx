import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("renders brand and primary navigation links", () => {
    render(
      <MemoryRouter>
        <AppShell />
      </MemoryRouter>,
    );

    expect(screen.getByText("Tax Tracker")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Income" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tax position" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View source on GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/ShoGinn/tax-tracker",
    );
    expect(screen.getByRole("heading", { name: "Your federal tax plan" })).toBeInTheDocument();
  });
});

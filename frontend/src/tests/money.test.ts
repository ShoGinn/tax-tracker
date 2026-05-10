import { describe, expect, it } from "vitest";

import { formatCurrency, parseDecimalString } from "../lib/money";

describe("parseDecimalString", () => {
  it("returns 0 for nullish values", () => {
    expect(parseDecimalString(null)).toBe(0);
    expect(parseDecimalString(undefined)).toBe(0);
  });

  it("parses currency strings and commas", () => {
    expect(parseDecimalString("$1,234.56")).toBe(1234.56);
    expect(parseDecimalString(" 2,500 ")).toBe(2500);
  });

  it("returns 0 for invalid numeric input", () => {
    expect(parseDecimalString("abc")).toBe(0);
    expect(parseDecimalString(Number.NaN)).toBe(0);
  });
});

describe("formatCurrency", () => {
  it("formats numbers as USD", () => {
    expect(formatCurrency(1234.56)).toBe("$1,234.56");
  });
});

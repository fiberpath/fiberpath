import { describe, expect, it } from "vitest";
import { parseNumericInput } from "./numericFields";

describe("parseNumericInput()", () => {
  it("parses float strings by default", () => {
    expect(parseNumericInput("3.14")).toBeCloseTo(3.14);
  });

  it("parses integer strings when integer flag is true", () => {
    expect(parseNumericInput("42", true)).toBe(42);
  });

  it("truncates decimals in integer mode", () => {
    expect(parseNumericInput("3.99", true)).toBe(3);
  });

  it("returns NaN for non-numeric input", () => {
    expect(parseNumericInput("abc")).toBeNaN();
  });

  it("handles empty string", () => {
    expect(parseNumericInput("")).toBeNaN();
  });

  it("handles negative numbers", () => {
    expect(parseNumericInput("-5.5")).toBeCloseTo(-5.5);
  });
});

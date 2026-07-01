import { describe, expect, it } from "vitest";
import {
  isValidOtp,
  isValidUzPhone,
  maskPhone,
  normalizeUzPhone,
} from "@/lib/phone";

describe("normalizeUzPhone", () => {
  it("normalizes a 9-digit national number", () => {
    expect(normalizeUzPhone("901234567")).toBe("+998901234567");
  });

  it("normalizes a number with spaces and a leading +998", () => {
    expect(normalizeUzPhone("+998 90 123 45 67")).toBe("+998901234567");
  });

  it("normalizes a number with 998 prefix but no plus", () => {
    expect(normalizeUzPhone("998901234567")).toBe("+998901234567");
  });

  it("rejects too-short input", () => {
    expect(normalizeUzPhone("12345")).toBeNull();
  });

  it("rejects too-long input", () => {
    expect(normalizeUzPhone("99890123456789")).toBeNull();
  });

  it("rejects empty input", () => {
    expect(normalizeUzPhone("")).toBeNull();
  });
});

describe("isValidUzPhone", () => {
  it("accepts a valid number", () => {
    expect(isValidUzPhone("901234567")).toBe(true);
  });

  it("rejects garbage", () => {
    expect(isValidUzPhone("abc")).toBe(false);
  });
});

describe("isValidOtp", () => {
  it("accepts exactly 6 digits", () => {
    expect(isValidOtp("123456")).toBe(true);
  });

  it("rejects fewer than 6 digits", () => {
    expect(isValidOtp("12345")).toBe(false);
  });

  it("rejects non-digit characters", () => {
    expect(isValidOtp("12a456")).toBe(false);
  });

  it("trims surrounding whitespace before checking", () => {
    expect(isValidOtp(" 123456 ")).toBe(true);
  });
});

describe("maskPhone", () => {
  it("masks the middle digits, keeping operator code and last two digits", () => {
    expect(maskPhone("+998901234567")).toBe("+998 90 123 ** 67");
  });

  it("returns the input unchanged if it doesn't match the expected shape", () => {
    expect(maskPhone("not-a-phone")).toBe("not-a-phone");
  });
});

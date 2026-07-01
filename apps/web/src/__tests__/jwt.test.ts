import { describe, expect, it } from "vitest";
import { decodeAccessToken, isExpired } from "@/lib/auth/jwt";

/**
 * Builds a syntactically valid compact JWT (header.payload.signature) with
 * an arbitrary (unverified) signature segment. decodeAccessToken only calls
 * jose's decodeJwt(), which never checks the signature — so this is enough
 * to exercise the claim-reading logic without fighting jsdom/jose's
 * Uint8Array realm checks in SignJWT.
 */
function makeToken(claims: Record<string, unknown>): string {
  const base64url = (input: string) =>
    Buffer.from(input, "utf8")
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");

  const header = base64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = base64url(JSON.stringify(claims));
  return `${header}.${payload}.unsigned-test-signature`;
}

describe("decodeAccessToken", () => {
  it("decodes a well-formed access token", async () => {
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const token = makeToken({ sub: "user-1", type: "access", exp });

    const payload = decodeAccessToken(token);
    expect(payload).toEqual({ sub: "user-1", type: "access", exp });
  });

  it("defaults type to 'access' if claim is missing or unrecognized", async () => {
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const token = makeToken({ sub: "user-1", exp });

    const payload = decodeAccessToken(token);
    expect(payload?.type).toBe("access");
  });

  it("returns null for garbage input", () => {
    expect(decodeAccessToken("not-a-jwt")).toBeNull();
  });

  it("returns null when sub is missing", async () => {
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const token = makeToken({ exp });
    expect(decodeAccessToken(token)).toBeNull();
  });

  it("returns null when exp is missing", async () => {
    const token = makeToken({ sub: "user-1" });
    expect(decodeAccessToken(token)).toBeNull();
  });
});

describe("isExpired", () => {
  it("returns false for a token expiring in the future", () => {
    const payload = {
      sub: "user-1",
      type: "access" as const,
      exp: Math.floor(Date.now() / 1000) + 3600,
    };
    expect(isExpired(payload)).toBe(false);
  });

  it("returns true for a token that already expired", () => {
    const payload = {
      sub: "user-1",
      type: "access" as const,
      exp: Math.floor(Date.now() / 1000) - 10,
    };
    expect(isExpired(payload)).toBe(true);
  });

  it("treats tokens within the clock-skew window as expired", () => {
    const payload = {
      sub: "user-1",
      type: "access" as const,
      exp: Math.floor(Date.now() / 1000) + 5, // expires in 5s, skew is 10s
    };
    expect(isExpired(payload, 10)).toBe(true);
  });
});

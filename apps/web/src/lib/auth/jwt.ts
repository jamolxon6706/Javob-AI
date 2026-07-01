import { decodeJwt } from "jose";

export interface AccessTokenPayload {
  sub: string;
  type: "access" | "refresh";
  exp: number;
}

/**
 * Decode (NOT verify) a JWT to peek at its claims. Used only in the Next.js
 * middleware to decide "should I redirect to /login" or "is this token close
 * to expiry, try a silent refresh". The actual cryptographic verification of
 * every API call happens in FastAPI (javobai.auth.deps.get_current_user),
 * which is the only place that holds JWT_SECRET. The web app never has that
 * secret, so it cannot and must not attempt signature verification.
 */
export function decodeAccessToken(token: string): AccessTokenPayload | null {
  try {
    const payload = decodeJwt(token);
    if (typeof payload.sub !== "string" || typeof payload.exp !== "number") {
      return null;
    }
    return {
      sub: payload.sub,
      type: payload.type === "refresh" ? "refresh" : "access",
      exp: payload.exp,
    };
  } catch {
    return null;
  }
}

export function isExpired(payload: AccessTokenPayload, skewSeconds = 10): boolean {
  const nowSeconds = Date.now() / 1000;
  return payload.exp - skewSeconds <= nowSeconds;
}

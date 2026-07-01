/**
 * Normalizes a free-typed Uzbek phone number into E.164 (+998XXXXXXXXX).
 * Accepts inputs like "90 123 45 67", "+998901234567", "998901234567".
 * Returns null if the result isn't a plausible Uzbek mobile number.
 */
export function normalizeUzPhone(raw: string): string | null {
  const digits = raw.replace(/\D/g, "");
  let national: string;

  if (digits.startsWith("998") && digits.length === 12) {
    national = digits.slice(3);
  } else if (digits.length === 9) {
    national = digits;
  } else {
    return null;
  }

  // Uzbek mobile operator prefixes are 2 digits, followed by 7 more digits.
  if (!/^\d{9}$/.test(national)) return null;

  return `+998${national}`;
}

export function isValidUzPhone(raw: string): boolean {
  return normalizeUzPhone(raw) !== null;
}

export function isValidOtp(raw: string): boolean {
  return /^\d{6}$/.test(raw.trim());
}

/** Masks a phone number for display: +998901234567 -> +998 90 123 ** 67 */
export function maskPhone(phone: string): string {
  const match = phone.match(/^\+998(\d{2})(\d{3})(\d{2})(\d{2})$/);
  if (!match) return phone;
  const [, op, mid, , last] = match;
  return `+998 ${op} ${mid} ** ${last}`;
}

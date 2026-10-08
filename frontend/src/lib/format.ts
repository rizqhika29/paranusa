const WEI = 10n ** 18n;

/** u256 wei -> compact GEN string, e.g. "1.5" */
export function weiToGen(wei: bigint | number | string): string {
  const w = typeof wei === "bigint" ? wei : BigInt(wei);
  const neg = w < 0n;
  const abs = neg ? -w : w;
  const whole = abs / WEI;
  const frac = abs % WEI;
  if (frac === 0n) return `${neg ? "-" : ""}${whole.toString()}`;
  const fracStr = frac.toString().padStart(18, "0").replace(/0+$/, "").slice(0, 6);
  return `${neg ? "-" : ""}${whole.toString()}.${fracStr}`;
}

/** GEN string -> wei bigint. Throws on bad format. */
export function genToWei(input: string): bigint {
  const s = input.trim().replace(",", ".");
  if (!/^\d+(\.\d{1,18})?$/.test(s)) throw new Error("Invalid GEN format (example: 1.5)");
  const [whole, fracRaw = ""] = s.split(".");
  const frac = (fracRaw + "0".repeat(18)).slice(0, 18);
  return BigInt(whole) * WEI + BigInt(frac);
}

export function shortAddress(addr: string, chars = 6): string {
  if (!addr) return "—";
  if (addr.length <= chars * 2 + 2) return addr;
  return `${addr.slice(0, chars + 2)}…${addr.slice(-chars)}`;
}

export function shortHash(hash: string, chars = 8): string {
  if (!hash) return "—";
  return `${hash.slice(0, chars + 2)}…${hash.slice(-6)}`;
}

export function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Extract the business message from a contract revert: "[EXPECTED] ..." -> "..." */
export function cleanRevertMessage(raw: string): string {
  const m = raw.match(/\[(EXPECTED|EXTERNAL|TRANSIENT)\]\s*(.*)/s);
  if (m) return m[2].trim().split("\n")[0];
  const short = raw.match(/reverted with reason string '([^']+)'/);
  if (short) return short[1];
  if (raw.length > 220) return raw.slice(0, 220) + "…";
  return raw;
}

export type ErrorKind =
  | "user-rejected"
  | "business"
  | "external"
  | "transient"
  | "funds"
  | "network"
  | "unknown";

export interface ClassifiedError {
  kind: ErrorKind;
  title: string;
  message: string;
  retryable: boolean;
}

/** Classify write errors so the UI can suggest the right next action. */
export function classifyWriteError(err: unknown): ClassifiedError {
  const raw = err instanceof Error ? `${err.message} ${String((err as { cause?: unknown }).cause ?? "")}` : String(err);
  const lower = raw.toLowerCase();

  if (
    lower.includes("user rejected") ||
    lower.includes("user denied") ||
    lower.includes("request rejected") ||
    (lower.includes("code") && lower.includes("4001"))
  ) {
    return {
      kind: "user-rejected",
      title: "Transaction cancelled",
      message: "You rejected the signature in your wallet. Nothing changed on-chain — safe to try again.",
      retryable: true,
    };
  }
  if (raw.includes("[EXPECTED]")) {
    return {
      kind: "business",
      title: "Rejected by contract",
      message: cleanRevertMessage(raw),
      retryable: false,
    };
  }
  if (raw.includes("[EXTERNAL]")) {
    return {
      kind: "external",
      title: "Data source issue",
      message: `${cleanRevertMessage(raw)} Try again in a few minutes.`,
      retryable: true,
    };
  }
  if (raw.includes("[TRANSIENT]")) {
    return {
      kind: "transient",
      title: "Temporary disruption",
      message: `${cleanRevertMessage(raw)} Wait a moment, then retry.`,
      retryable: true,
    };
  }
  if (lower.includes("insufficient") || lower.includes("exceeds balance")) {
    return {
      kind: "funds",
      title: "Insufficient GEN",
      message: "Your wallet cannot cover value + fees. Top up from the active network faucet first.",
      retryable: true,
    };
  }
  if (
    lower.includes("failed to fetch") ||
    lower.includes("networkerror") ||
    lower.includes("econnrefused") ||
    lower.includes("timeout")
  ) {
    return {
      kind: "network",
      title: "RPC unreachable",
      message: "Cannot reach the GenLayer node. Check your connection or switch networks.",
      retryable: true,
    };
  }
  return {
    kind: "unknown",
    title: "Transaction failed",
    message: cleanRevertMessage(raw),
    retryable: true,
  };
}

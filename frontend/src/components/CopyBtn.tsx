"use client";
import { useState } from "react";
import { useApp } from "@/state/AppContext";

/** Small copy-to-clipboard button with confirmation feedback. */
export default function CopyBtn({ value, label }: { value: string; label: string }) {
  const { pushToast } = useApp();
  const [done, setDone] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setDone(true);
      window.setTimeout(() => setDone(false), 1500);
    } catch {
      pushToast({ tone: "error", title: "Copy failed", message: `Could not copy ${label}.` });
    }
  }

  return (
    <button
      className="btn btn-ghost btn-sm"
      onClick={copy}
      title={`Copy ${label}`}
      aria-label={`Copy ${label}`}
    >
      {done ? "✓ Copied" : "⧉ Copy"}
    </button>
  );
}

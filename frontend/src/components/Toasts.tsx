"use client";
import { useApp } from "@/state/AppContext";
import { NETWORKS } from "@/lib/config";
import { shortHash } from "@/lib/format";

export default function Toasts() {
  const { toasts, dismissToast, network } = useApp();
  const explorer = NETWORKS[network].explorerTx;
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.tone}`}>
          <button className="x" onClick={() => dismissToast(t.id)} aria-label="Close">
            ×
          </button>
          <strong>{t.title}</strong>
          <p>{t.message}</p>
          {t.txHash && explorer(t.txHash) && (
            <p>
              <a
                className="tx-hash"
                href={explorer(t.txHash as string) as string}
                target="_blank"
                rel="noreferrer"
              >
                View in explorer: {shortHash(t.txHash)}
              </a>
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

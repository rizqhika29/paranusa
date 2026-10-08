import Link from "next/link";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="wrap footer-inner">
        <div>
          <strong style={{ color: "var(--text)" }}>ParaNusa</strong> — Parametric
          disaster insurance for the archipelago.
          <br />
          Drought · Flood · Earthquake on GenLayer consensus.
        </div>
        <div style={{ display: "flex", gap: 16 }}>
          <Link href="/how-it-works">How It Works</Link>
          <Link href="/app">App</Link>
          <Link href="/profile">Profile</Link>
          <a href="https://docs.genlayer.com" target="_blank" rel="noreferrer">
            GenLayer Docs
          </a>
        </div>
      </div>
    </footer>
  );
}

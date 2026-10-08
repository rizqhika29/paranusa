"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useApp } from "@/state/AppContext";
import { NETWORKS } from "@/lib/config";
import { shortAddress } from "@/lib/format";

export default function Navbar() {
  const pathname = usePathname();
  const { network, wallet, connecting, connectWallet, disconnectWallet } = useApp();
  const is = (p: string) => (pathname === p ? "active" : "");

  return (
    <header className="nav">
      <div className="wrap nav-inner">
        <Link href="/" className="brand">
          <span className="brand-mark">P</span>
          ParaNusa
        </Link>
        <nav className="nav-links">
          <Link href="/" className={is("/")}>Home</Link>
          <Link href="/how-it-works" className={is("/how-it-works")}>How It Works</Link>
          <Link href="/app" className={is("/app")}>App</Link>
          <Link href="/profile" className={is("/profile")}>Profile</Link>
        </nav>
        <div className="nav-right">
          <span className="pill pill-idle" title="Active GenLayer network">
            {NETWORKS[network].label}
          </span>
          {wallet ? (
            <button
              className="btn btn-ghost btn-sm"
              onClick={disconnectWallet}
              title={wallet}
            >
              {shortAddress(wallet)}
            </button>
          ) : (
            <button className="btn btn-primary btn-sm" onClick={connectWallet} disabled={connecting}>
              {connecting ? "Connecting…" : "Connect Wallet"}
            </button>
          )}
          <details className="mobile-menu">
            <summary className="btn btn-ghost btn-sm" aria-label="Menu">☰</summary>
            <div className="mobile-menu-list">
              <Link href="/">Home</Link>
              <Link href="/how-it-works">How It Works</Link>
              <Link href="/app">App</Link>
              <Link href="/profile">Profile</Link>
            </div>
          </details>
        </div>
      </div>
    </header>
  );
}

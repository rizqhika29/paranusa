import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { AppProvider } from "@/state/AppContext";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import Toasts from "@/components/Toasts";

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "ParaNusa — Parametric Disaster Insurance for the Archipelago",
  description:
    "Drought, flood, and earthquake policies that pay automatically from real-world data — assessed by GenLayer AI-validator consensus.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={jakarta.className}>
        <AppProvider>
          <div className="page">
            <Navbar />
            <main>{children}</main>
            <Footer />
          </div>
          <Toasts />
        </AppProvider>
      </body>
    </html>
  );
}

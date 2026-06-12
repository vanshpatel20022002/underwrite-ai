import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Real Estate Underwriting AI",
  description: "Agentic property underwriting with comps, ML valuation, and cited reports",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav
          style={{
            borderBottom: "1px solid var(--border)",
            padding: "1rem 2rem",
            display: "flex",
            gap: "1.5rem",
            alignItems: "center",
          }}
        >
          <strong>Underwriting AI</strong>
          <a href="/">Cases</a>
          <a href="/cases/new">New Case</a>
        </nav>
        {children}
      </body>
    </html>
  );
}

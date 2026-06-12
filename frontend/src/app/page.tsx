"use client";

import { useEffect, useState } from "react";
import { Case, fetchCases, checkHealth } from "@/lib/api";

export default function HomePage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [apiStatus, setApiStatus] = useState<string>("checking...");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    checkHealth()
      .then((h) => setApiStatus(h.status))
      .catch(() => setApiStatus("offline"));

    fetchCases()
      .then(setCases)
      .catch((e) => setError(e.message));
  }, []);

  const badgeClass = (rec?: string) => {
    if (rec === "approve") return "badge badge-approve";
    if (rec === "reject") return "badge badge-reject";
    return "badge badge-review";
  };

  return (
    <div className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1>Underwriting Cases</h1>
          <p style={{ color: "var(--muted)" }}>API status: {apiStatus}</p>
        </div>
        <a href="/cases/new" className="btn">
          New Case
        </a>
      </div>

      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}

      {cases.length === 0 && !error && (
        <div className="card" style={{ marginTop: "2rem" }}>
          <p>No cases yet. Create your first underwriting case.</p>
        </div>
      )}

      {cases.map((c) => (
        <a key={c.id} href={`/cases/${c.id}`} style={{ display: "block" }}>
          <div className="card" style={{ cursor: "pointer" }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div>
                <strong>{c.input.address}</strong>
                <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                  {c.input.bedrooms}bd / {c.input.bathrooms}ba / {c.input.square_footage} sqft
                </p>
              </div>
              <div style={{ textAlign: "right" }}>
                <span className={badgeClass(c.report?.recommendation)}>
                  {c.report?.recommendation || c.workflow_status}
                </span>
                <p style={{ color: "var(--muted)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                  Ingestion: {c.ingestion_status}
                </p>
              </div>
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}

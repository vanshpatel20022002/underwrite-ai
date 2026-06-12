"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import CompMap from "@/components/CompMap";
import { Case, fetchCase, resumeWorkflow, runWorkflow } from "@/lib/api";

export default function CaseDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCase = useCallback(async () => {
    try {
      const data = await fetchCase(id);
      setCaseData(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadCase();
    const interval = setInterval(loadCase, 5000);
    return () => clearInterval(interval);
  }, [loadCase]);

  async function handleRunWorkflow() {
    setActionLoading(true);
    setError(null);
    try {
      await runWorkflow(id);
      await loadCase();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Workflow failed");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleHumanReview(approved: boolean) {
    setActionLoading(true);
    try {
      await resumeWorkflow(id, approved);
      await loadCase();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resume failed");
    } finally {
      setActionLoading(false);
    }
  }

  function exportJson() {
    if (!caseData?.report) return;
    const blob = new Blob([JSON.stringify(caseData.report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `underwriting-${id}.json`;
    a.click();
  }

  if (loading) return <div className="container"><p>Loading...</p></div>;
  if (!caseData) return <div className="container"><p>Case not found</p></div>;

  const report = caseData.report;
  const awaitingReview = caseData.workflow_status === "awaiting_human_review";

  const badgeClass =
    report?.recommendation === "approve"
      ? "badge badge-approve"
      : report?.recommendation === "reject"
        ? "badge badge-reject"
        : "badge badge-review";

  return (
    <div className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1>{caseData.input.address}</h1>
          <p style={{ color: "var(--muted)" }}>
            {caseData.input.bedrooms}bd / {caseData.input.bathrooms}ba /{" "}
            {caseData.input.square_footage} sqft
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          {caseData.ingestion_status === "completed" && !report && (
            <button className="btn" onClick={handleRunWorkflow} disabled={actionLoading}>
              Run Underwriting
            </button>
          )}
          {report && (
            <button className="btn btn-secondary" onClick={exportJson}>
              Export JSON
            </button>
          )}
        </div>
      </div>

      {error && <p style={{ color: "var(--danger)", marginTop: "1rem" }}>{error}</p>}

      <div className="card" style={{ marginTop: "1rem" }}>
        <strong>Status</strong>
        <p>
          Ingestion: {caseData.ingestion_status} | Workflow: {caseData.workflow_status}
        </p>
      </div>

      {awaitingReview && (
        <div className="card" style={{ borderColor: "var(--warning)" }}>
          <h3>Human Review Required</h3>
          <p>Review risk assessment before final report generation.</p>
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
            <button
              className="btn btn-success"
              onClick={() => handleHumanReview(true)}
              disabled={actionLoading}
            >
              Approve & Generate Report
            </button>
            <button
              className="btn btn-danger"
              onClick={() => handleHumanReview(false)}
              disabled={actionLoading}
            >
              Reject
            </button>
          </div>
        </div>
      )}

      {report && (
        <>
          <div className="grid-2" style={{ marginTop: "1rem" }}>
            <div className="card">
              <h3>Valuation</h3>
              <p style={{ fontSize: "2rem", fontWeight: 700 }}>
                ${report.estimated_value?.toLocaleString() ?? "N/A"}
              </p>
              {report.confidence_interval && (
                <p style={{ color: "var(--muted)" }}>
                  CI: ${report.confidence_interval.low.toLocaleString()} – $
                  {report.confidence_interval.high.toLocaleString()}
                </p>
              )}
              <p>Confidence: {((report.confidence_score ?? 0) * 100).toFixed(0)}%</p>
              <span className={badgeClass}>{report.recommendation}</span>
            </div>
            <div className="card">
              <h3>Risk Score</h3>
              <p style={{ fontSize: "2rem", fontWeight: 700 }}>{report.risk_score?.toFixed(0)}/100</p>
              {report.risk_flags?.map((f) => (
                <p key={f.code} style={{ fontSize: "0.85rem", color: "var(--warning)" }}>
                  [{f.severity}] {f.message}
                </p>
              ))}
            </div>
          </div>

          {report.top_5_comps && report.top_5_comps.length > 0 && (
            <>
              <div className="card" style={{ marginTop: "1rem" }}>
                <h3>Comparable Sales Map</h3>
                <CompMap
                  subjectLat={(caseData.input as { latitude?: number }).latitude}
                  subjectLon={(caseData.input as { longitude?: number }).longitude}
                  comps={report.top_5_comps}
                />
              </div>

              <div className="card">
                <h3>Top 5 Comparables</h3>
                <table>
                  <thead>
                    <tr>
                      <th>Address</th>
                      <th>Sale Price</th>
                      <th>Adjusted</th>
                      <th>Distance</th>
                      <th>Similarity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.top_5_comps.map((c) => (
                      <tr key={c.id}>
                        <td>{c.address}</td>
                        <td>${c.sale_price.toLocaleString()}</td>
                        <td>${(c.adjusted_price ?? c.sale_price).toLocaleString()}</td>
                        <td>{c.distance_miles} mi</td>
                        <td>{(c.similarity_score * 100).toFixed(0)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {report.adjustment_table && report.adjustment_table.length > 0 && (
            <div className="card">
              <h3>Adjustment Table</h3>
              <table>
                <thead>
                  <tr>
                    <th>Comp</th>
                    <th>Factor</th>
                    <th>Subject</th>
                    <th>Comp</th>
                    <th>Adjustment</th>
                  </tr>
                </thead>
                <tbody>
                  {report.adjustment_table.map((a, i) => (
                    <tr key={i}>
                      <td>{a.comp_id}</td>
                      <td>{a.factor}</td>
                      <td>{a.subject_value}</td>
                      <td>{a.comp_value}</td>
                      <td>${a.adjustment_amount.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {report.shap_features && report.shap_features.length > 0 && (
            <div className="card">
              <h3>SHAP Feature Importance</h3>
              {report.shap_features.map((s) => (
                <p key={s.feature}>
                  {s.feature}: {s.contribution > 0 ? "+" : ""}${s.contribution.toLocaleString()}
                </p>
              ))}
            </div>
          )}

          {report.citations && report.citations.length > 0 && (
            <div className="card">
              <h3>Citations</h3>
              {report.citations.map((c, i) => (
                <div key={i} style={{ marginBottom: "1rem", paddingBottom: "1rem", borderBottom: "1px solid var(--border)" }}>
                  <strong>
                    [{c.doc_type}] {c.source_file} p.{c.page ?? "?"}
                  </strong>
                  <p style={{ fontSize: "0.9rem", color: "var(--muted)" }}>{c.snippet}</p>
                </div>
              ))}
            </div>
          )}

          {report.memo_markdown && (
            <div className="card">
              <h3>Underwriting Memo</h3>
              <div className="memo-content">
                <ReactMarkdown>{report.memo_markdown}</ReactMarkdown>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

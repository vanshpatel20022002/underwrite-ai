"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createCase } from "@/lib/api";

export default function NewCasePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const form = e.currentTarget;
    const formData = new FormData(form);

    try {
      const caseData = await createCase(formData);
      router.push(`/cases/${caseData.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create case");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container">
      <h1>New Underwriting Case</h1>
      <p style={{ color: "var(--muted)", marginBottom: "1.5rem" }}>
        Upload property details, documents, and images for automated underwriting.
      </p>

      <form onSubmit={handleSubmit} className="card">
        <div className="grid-2">
          <div>
            <label>Address *</label>
            <input name="address" required placeholder="123 Main St SE, Calgary, AB" />
          </div>
          <div>
            <label>Property Type</label>
            <select name="property_type" defaultValue="single_family">
              <option value="single_family">Single Family</option>
              <option value="condo">Condo</option>
              <option value="townhouse">Townhouse</option>
              <option value="multi_family">Multi Family</option>
            </select>
          </div>
          <div>
            <label>Bedrooms *</label>
            <input name="bedrooms" type="number" required defaultValue={3} />
          </div>
          <div>
            <label>Bathrooms *</label>
            <input name="bathrooms" type="number" step="0.5" required defaultValue={2} />
          </div>
          <div>
            <label>Square Footage *</label>
            <input name="square_footage" type="number" required defaultValue={1800} />
          </div>
          <div>
            <label>Lot Size (sqft)</label>
            <input name="lot_size" type="number" defaultValue={6000} />
          </div>
          <div>
            <label>Year Built</label>
            <input name="year_built" type="number" defaultValue={1995} />
          </div>
        </div>

        <label>Listing Description</label>
        <textarea name="listing_description" rows={3} placeholder="Property listing details..." />

        <label>Borrower Notes</label>
        <textarea name="borrower_notes" rows={2} placeholder="Optional borrower notes..." />

        <div className="grid-2" style={{ marginTop: "1rem" }}>
          <div>
            <label>Appraisal PDF</label>
            <input name="appraisal_pdf" type="file" accept=".pdf" />
          </div>
          <div>
            <label>Zoning PDF</label>
            <input name="zoning_pdf" type="file" accept=".pdf" />
          </div>
          <div>
            <label>Market Data (CSV/Parquet)</label>
            <input name="market_file" type="file" accept=".csv,.parquet" />
          </div>
          <div>
            <label>Property Images (5-10)</label>
            <input name="images" type="file" accept="image/*" multiple />
          </div>
        </div>

        {error && <p style={{ color: "var(--danger)", marginTop: "1rem" }}>{error}</p>}

        <button type="submit" className="btn" disabled={loading} style={{ marginTop: "1.5rem" }}>
          {loading ? "Creating..." : "Create Case"}
        </button>
      </form>
    </div>
  );
}

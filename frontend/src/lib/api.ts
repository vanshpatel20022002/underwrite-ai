const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface CaseInput {
  address: string;
  property_type: string;
  bedrooms: number;
  bathrooms: number;
  square_footage: number;
  lot_size?: number;
  year_built?: number;
  listing_description: string;
  borrower_notes: string;
}

export interface Case {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  input: CaseInput;
  report?: Report;
  ingestion_status: string;
  workflow_status: string;
}

export interface Report {
  estimated_value?: number;
  confidence_score?: number;
  confidence_interval?: { low: number; high: number; level: number };
  top_5_comps?: Comp[];
  adjustment_table?: Adjustment[];
  risk_score?: number;
  risk_flags?: RiskFlag[];
  image_condition_notes?: ImageNote[];
  citations?: Citation[];
  shap_features?: ShapFeature[];
  memo_markdown?: string;
  recommendation?: string;
}

export interface Comp {
  id: string;
  address: string;
  sale_price: number;
  sale_date: string;
  bedrooms: number;
  bathrooms: number;
  square_footage: number;
  distance_miles: number;
  similarity_score: number;
  adjusted_price?: number;
  latitude?: number;
  longitude?: number;
}

export interface Adjustment {
  comp_id: string;
  factor: string;
  subject_value: string;
  comp_value: string;
  adjustment_amount: number;
  notes: string;
}

export interface RiskFlag {
  code: string;
  severity: string;
  message: string;
  evidence?: string;
}

export interface ImageNote {
  image_path: string;
  condition: string;
  risk_level: string;
  confidence: number;
}

export interface Citation {
  doc_type: string;
  page?: number;
  section?: string;
  snippet: string;
  source_file?: string;
}

export interface ShapFeature {
  feature: string;
  contribution: number;
}

export async function fetchCases(): Promise<Case[]> {
  const res = await fetch(`${API_URL}/api/v1/cases`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch cases");
  return res.json();
}

export async function fetchCase(id: string): Promise<Case> {
  const res = await fetch(`${API_URL}/api/v1/cases/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch case");
  return res.json();
}

export async function createCase(formData: FormData): Promise<Case> {
  const res = await fetch(`${API_URL}/api/v1/cases`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error("Failed to create case");
  return res.json();
}

export async function runWorkflow(caseId: string): Promise<unknown> {
  const res = await fetch(`${API_URL}/api/v1/workflow/${caseId}/run`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || "Workflow failed");
  }
  return res.json();
}

export async function resumeWorkflow(caseId: string, approved: boolean): Promise<unknown> {
  const res = await fetch(
    `${API_URL}/api/v1/workflow/${caseId}/resume?approved=${approved}`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error("Resume failed");
  return res.json();
}

export async function checkHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_URL}/health`);
  return res.json();
}

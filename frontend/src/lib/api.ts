export type Band = "auto_fill" | "needs_review" | "reviewed" | "blank";

export interface MappedField {
  id: string;
  page: number;
  field_name: string | null;
  field_type: string;
  label: string | null;
  section: string | null;
  chosen_key: string | null;
  value: string | null;
  confidence: number;
  band: Band;
  layer: string;
  reasons: string[];
}

export interface JobSummary {
  id: string;
  cv_name: string;
  form_name: string;
  status: "queued" | "extracting" | "mapping" | "filling" | "needs_review" | "completed" | "failed";
  review_status: "pending" | "approved" | "rejected";
  review_note: string | null;
  error: string | null;
  counts: Partial<Record<Band, number>>;
  progress: number;
  created_at: string;
  updated_at: string;
}

export interface JobDetail extends JobSummary {
  warnings: string[];
  fields: MappedField[];
}

export interface AdminJob extends JobSummary {
  applicant: string;
  email: string;
}

export interface Me {
  email: string;
  is_admin: boolean;
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/backend/${path}`, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.error ?? "Request failed", response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export async function uploadFile(file: File): Promise<string> {
  const query = new URLSearchParams({ fileName: file.name, fileType: file.type });
  const presign = await fetch(`/api/upload?${query}`);
  const body = await presign.json();
  if (!presign.ok) throw new Error(body.error ?? "Could not prepare the upload");
  const upload = await fetch(body.uploadUrl, { method: "PUT", headers: body.headers, body: file });
  if (!upload.ok) throw new Error(`Could not upload ${file.name}`);
  return body.key;
}

export function fieldTitle(field: MappedField): string {
  const name = field.field_name ?? "";
  const generic = /^(text|check box|undefined|signature)\s*\d*$/i.test(name);
  return (generic ? field.label : name.replace(/_\d+$/, "").replace(/^\d+[A-Z]?\s+/, "")) || field.label || name;
}

export const STATUS_LABELS: Record<JobSummary["status"], string> = {
  queued: "Queued",
  extracting: "Reading the provider document",
  mapping: "Matching data to form fields",
  filling: "Filling the form",
  needs_review: "Needs review",
  completed: "Completed",
  failed: "Failed",
};

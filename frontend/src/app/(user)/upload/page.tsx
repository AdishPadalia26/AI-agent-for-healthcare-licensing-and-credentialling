"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { ArrowLeft, Download } from "lucide-react";
import { STATUS_LABELS, api, fieldTitle, uploadFile, type JobDetail, type MappedField } from "@/lib/api";

const PdfViewer = dynamic(() => import("@/components/PdfViewer"), {
  ssr: false,
  loading: () => <p className="p-8 text-gray-500">Loading viewer…</p>,
});

const POLL_MS = 2000;
const INPUT_CLASS =
  "mt-1 block w-full rounded-md border border-gray-400 px-3 py-2 text-gray-900 focus:ring-2 focus:ring-black focus:outline-none";

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good Morning" : hour < 18 ? "Good Afternoon" : "Good Evening";
}

function isFinished(job: JobDetail) {
  return ["needs_review", "completed", "failed"].includes(job.status);
}

function UploadForm({ onStarted }: { onStarted: (jobId: string) => void }) {
  const { data: session } = useSession();
  const [cv, setCv] = useState<File | null>(null);
  const [form, setForm] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    if (!cv || !form) {
      setError("Choose both a provider document and a form.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const [cvKey, formKey] = await Promise.all([uploadFile(cv), uploadFile(form)]);
      const job = await api<{ id: string }>("jobs", {
        method: "POST",
        body: JSON.stringify({ cv_key: cvKey, form_key: formKey, cv_name: cv.name, form_name: form.name }),
      });
      onStarted(job.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col justify-center items-center w-full min-h-screen px-4">
      <h1 className="text-3xl mb-4 font-semibold">
        {greeting()}, <span className="text-orange-600">{session?.user?.name ?? session?.user?.email ?? ""}</span>
      </h1>
      <h2 className="text-2xl text-center">Automate Healthcare Licensing &amp; Credentialing in Minutes</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 pt-4 w-full max-w-3xl mt-12">
        <div>
          <label htmlFor="upload-main" className="block text-lg font-medium text-gray-700 mb-2">
            1. Provider Document (e.g., CV)
          </label>
          <input
            type="file"
            id="upload-main"
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={(e) => setCv(e.target.files?.[0] ?? null)}
            className="w-full cursor-pointer text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:font-semibold file:bg-blue-50 file:text-blue-700"
          />
        </div>
        <div>
          <label htmlFor="upload-form" className="block text-lg font-medium text-gray-700 mb-2">
            2. Fillable PDF Form
          </label>
          <input
            type="file"
            id="upload-form"
            accept=".pdf"
            onChange={(e) => setForm(e.target.files?.[0] ?? null)}
            className="w-full cursor-pointer text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:font-semibold file:bg-green-50 file:text-green-700"
          />
        </div>
      </div>
      {error && <p className="text-sm text-red-600 mt-6">{error}</p>}
      <button
        onClick={start}
        disabled={busy}
        className="px-8 py-3 mt-12 font-bold rounded-xl shadow-lg bg-orange-300 hover:bg-orange-500 disabled:bg-gray-400"
      >
        {busy ? "Uploading…" : "Start AI Extraction"}
      </button>
    </div>
  );
}

function ReviewField({
  field,
  value,
  onChange,
}: {
  field: MappedField;
  value: string;
  onChange: (value: string) => void;
}) {
  const id = `review-${field.id}`;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-800">
        {fieldTitle(field)}
      </label>
      <input id={id} type="text" value={value} onChange={(e) => onChange(e.target.value)} className={INPUT_CLASS} />
      {field.band === "needs_review" && (
        <p className="text-xs text-amber-700 mt-1">
          {Math.round(field.confidence * 100)}% confidence{field.reasons.length ? ` · ${field.reasons.join("; ")}` : ""}
        </p>
      )}
    </div>
  );
}

function Review({ job, onChanged, onBack }: { job: JobDetail; onChanged: (job: JobDetail) => void; onBack: () => void }) {
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [showBlank, setShowBlank] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  const review = useMemo(() => job.fields.filter((f) => f.band === "needs_review"), [job.fields]);
  const blank = useMemo(() => job.fields.filter((f) => f.band === "blank" && f.field_type === "text"), [job.fields]);
  const locked = job.review_status === "approved";

  function payload() {
    const accepted = review.map((f) => ({ id: f.id, value: edits[f.id] ?? f.value ?? "" }));
    const added = blank.filter((f) => edits[f.id]?.trim()).map((f) => ({ id: f.id, value: edits[f.id] }));
    return JSON.stringify({ fields: [...accepted, ...added] });
  }

  async function submit() {
    setBusy(true);
    setMessage(null);
    try {
      await api<JobDetail>(`jobs/${job.id}/fields`, { method: "PATCH", body: payload() });
      const finished = await api<JobDetail>(`jobs/${job.id}/finalize`, { method: "POST" });
      onChanged(finished);
      setEdits({});
      setVersion((v) => v + 1);
      setMessage("Saved. The PDF now includes your confirmed values.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  const value = (f: MappedField) => edits[f.id] ?? f.value ?? "";
  const change = (id: string) => (next: string) => setEdits((all) => ({ ...all, [id]: next }));
  const pdfUrl = `/api/backend/jobs/${job.id}/pdf?v=${version}`;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 w-full min-h-screen bg-white">
      <section className="lg:col-span-8 px-6 lg:px-12 py-8 overflow-auto border-r border-gray-200">
        <div className="flex justify-between mb-3 items-center">
          <h1 className="text-3xl font-semibold">Filled Form</h1>
          <div className="flex gap-3">
            <button aria-label="Back" onClick={onBack} className="bg-gray-200 hover:bg-gray-300 p-2 rounded-xl">
              <ArrowLeft />
            </button>
            <a
              aria-label="Download PDF"
              href={`/api/backend/jobs/${job.id}/pdf?download=1`}
              className="bg-blue-300 hover:bg-blue-500 p-2 rounded-xl"
            >
              <Download />
            </a>
          </div>
        </div>
        <PdfViewer url={pdfUrl} />
      </section>
      <aside className="lg:col-span-4 p-6 lg:p-8 overflow-auto lg:h-screen">
        <h2 className="text-xl font-semibold text-gray-800 mb-1">Review Details</h2>
        <p className="text-gray-600 mb-4 text-sm">
          {job.counts.auto_fill ?? 0} filled automatically · {review.length} to confirm · {job.counts.reviewed ?? 0}{" "}
          confirmed · {job.counts.blank ?? 0} left blank
        </p>
        {job.warnings.map((warning) => (
          <p key={warning} className="text-xs text-amber-700 mb-2">
            {warning}
          </p>
        ))}
        <div className="space-y-4">
          {review.length === 0 && <p className="text-sm text-gray-600">No low-confidence values to confirm.</p>}
          {review.map((f) => (
            <ReviewField key={f.id} field={f} value={value(f)} onChange={change(f.id)} />
          ))}
          <button type="button" onClick={() => setShowBlank((s) => !s)} className="text-sm text-blue-700 underline">
            {showBlank ? "Hide" : "Show"} {blank.length} blank fields
          </button>
          {showBlank && blank.map((f) => <ReviewField key={f.id} field={f} value={value(f)} onChange={change(f.id)} />)}
          {message && <p className="text-sm text-gray-700">{message}</p>}
          <button
            onClick={submit}
            disabled={busy || locked}
            className="w-full bg-green-300 py-2 rounded-md hover:bg-green-500 transition disabled:opacity-50"
          >
            {locked ? "Approved" : busy ? "Saving…" : "Save & Submit"}
          </button>
        </div>
      </aside>
    </div>
  );
}

function UploadPage() {
  const router = useRouter();
  const jobId = useSearchParams().get("job");
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    try {
      setJob(await api<JobDetail>(`jobs/${id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this application");
    }
  }, []);

  useEffect(() => {
    setJob(null);
    setError(null);
    if (jobId) void load(jobId);
  }, [jobId, load]);

  useEffect(() => {
    if (!jobId || !job || isFinished(job)) return;
    const timer = setTimeout(() => void load(jobId), POLL_MS);
    return () => clearTimeout(timer);
  }, [job, jobId, load]);

  const reset = () => router.push("/upload");

  if (!jobId) return <UploadForm onStarted={(id) => router.push(`/upload?job=${id}`)} />;
  if (error) return <Notice title="Something went wrong" detail={error} onBack={reset} />;
  if (!job) return <Notice title="Loading…" />;
  if (job.status === "failed") return <Notice title="Processing failed" detail={job.error ?? undefined} onBack={reset} />;
  if (!isFinished(job)) return <Notice title={`🤖 ${STATUS_LABELS[job.status]}…`} detail="This can take a few minutes." />;
  return <Review job={job} onChanged={setJob} onBack={reset} />;
}

function Notice({ title, detail, onBack }: { title: string; detail?: string; onBack?: () => void }) {
  return (
    <div className="flex flex-col justify-center items-center w-full min-h-screen gap-3 px-4 text-center">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {detail && <p className="text-gray-600">{detail}</p>}
      {onBack && (
        <button onClick={onBack} className="mt-4 bg-gray-200 hover:bg-gray-300 py-2 px-4 rounded-xl">
          Start over
        </button>
      )}
    </div>
  );
}

export default function Upload() {
  return (
    <div className="w-full">
      <Suspense fallback={<Notice title="Loading…" />}>
        <UploadPage />
      </Suspense>
    </div>
  );
}

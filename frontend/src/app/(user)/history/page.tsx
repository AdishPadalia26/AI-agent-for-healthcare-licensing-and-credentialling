"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { FileText } from "lucide-react";
import { STATUS_LABELS, api, type JobSummary } from "@/lib/api";

const REVIEW_LABELS = { pending: "Awaiting admin", approved: "Approved", rejected: "Rejected" };

export default function HistoryPage() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setJobs((await api<{ jobs: JobSummary[] }>("jobs")).jobs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load history");
    }
  }, []);

  useEffect(() => void load(), [load]);

  async function remove(job: JobSummary) {
    if (!window.confirm(`Delete ${job.form_name} and its uploaded files? This cannot be undone.`)) return;
    try {
      await api(`jobs/${job.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete");
    }
  }

  const completed = jobs?.filter((job) => job.status === "completed").length ?? 0;

  return (
    <div className="min-h-screen w-full bg-gray-50 px-6 py-10 flex flex-col items-center">
      <div className="max-w-6xl w-full mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-gray-300 text-gray-800 p-2 rounded-full">
            <FileText size={24} />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Form History</h1>
        </div>
        <p className="text-gray-700">View and manage all your submitted and in-progress forms</p>
        {jobs && (
          <div className="flex gap-6 mt-3 text-sm font-medium">
            <span className="text-gray-900">
              Total Forms: <span className="font-bold">{jobs.length}</span>
            </span>
            <span className="text-green-700">
              Completed: <span className="font-bold">{completed}</span>
            </span>
            <span className="text-amber-700">
              Incomplete: <span className="font-bold">{jobs.length - completed}</span>
            </span>
          </div>
        )}
      </div>

      {error && <p className="text-red-600 mb-4">{error}</p>}
      {jobs?.length === 0 && (
        <p className="text-gray-600">
          No forms yet.{" "}
          <Link className="text-blue-700 underline" href="/upload">
            Upload your first CV
          </Link>
          .
        </p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl w-full">
        {jobs?.map((job) => {
          const done = job.status === "completed";
          return (
            <div key={job.id} className="bg-white rounded-lg shadow-md p-6 flex flex-col justify-between">
              <div className="flex items-start justify-between mb-3 gap-2">
                <h2 className="text-lg font-semibold text-gray-900 break-all">{job.form_name}</h2>
                <span
                  className={`text-xs px-2 py-1 rounded-full font-semibold whitespace-nowrap ${
                    done ? "bg-green-200 text-green-800" : job.status === "failed" ? "bg-red-200 text-red-800" : "bg-amber-200 text-amber-800"
                  }`}
                >
                  {done ? REVIEW_LABELS[job.review_status] : STATUS_LABELS[job.status]}
                </span>
              </div>
              <p className="text-gray-700 text-sm mb-4 break-all">From {job.cv_name}</p>
              {job.error && <p className="text-red-600 text-sm mb-4">{job.error}</p>}
              {job.review_note && <p className="text-gray-700 text-sm mb-4">Note: {job.review_note}</p>}
              {job.status === "needs_review" && (
                <div className="mb-3">
                  <div className="flex justify-between text-xs mb-1 text-gray-800 font-medium">
                    <span>Progress</span>
                    <span>{job.progress}%</span>
                  </div>
                  <div className="w-full bg-gray-200 h-2 rounded-full overflow-hidden">
                    <div className="bg-black h-2" style={{ width: `${job.progress}%` }} />
                  </div>
                </div>
              )}
              <p className="text-gray-600 text-xs mb-4">Last updated: {new Date(job.updated_at).toLocaleString()}</p>
              <div className="flex gap-2">
                {job.status !== "failed" && (
                  <Link
                    href={`/upload?job=${job.id}`}
                    className="flex-1 text-center border border-gray-400 text-gray-800 rounded-md py-2 text-sm hover:bg-gray-100"
                  >
                    {done ? "View" : "Continue"}
                  </Link>
                )}
                {(done || job.status === "needs_review") && (
                  <a
                    href={`/api/backend/jobs/${job.id}/pdf?download=1`}
                    className="flex-1 text-center bg-black text-white rounded-md py-2 text-sm hover:bg-gray-800"
                  >
                    Download
                  </a>
                )}
                <button
                  onClick={() => remove(job)}
                  className="flex-1 border border-red-300 text-red-700 rounded-md py-2 text-sm hover:bg-red-50"
                >
                  Delete
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

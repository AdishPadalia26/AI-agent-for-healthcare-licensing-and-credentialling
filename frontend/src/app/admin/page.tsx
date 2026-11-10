"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Clock, FileText, Mail, User, X } from "lucide-react";
import { ApiError, api, type AdminJob } from "@/lib/api";

export default function AdminDashboardPage() {
  const [jobs, setJobs] = useState<AdminJob[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setJobs((await api<{ jobs: AdminJob[] }>("admin/jobs")).jobs);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 403 ? "You do not have admin access." : "Could not load applications.");
    }
  }, []);

  useEffect(() => void load(), [load]);

  async function decide(job: AdminJob, decision: "approved" | "rejected") {
    const note = decision === "rejected" ? window.prompt("Reason for rejection (shared with the applicant)") : "";
    if (note === null) return;
    try {
      await api(`admin/jobs/${job.id}/decision`, { method: "POST", body: JSON.stringify({ decision, note }) });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the decision");
    }
  }

  const pending = jobs?.filter((job) => job.review_status === "pending") ?? [];

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center px-4 py-10">
      <div className="max-w-4xl w-full mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Admin Dashboard</h1>
        <p className="text-gray-600">Review and manage practitioner license form applications</p>
      </div>
      <div className="bg-white rounded-lg shadow-lg max-w-4xl w-full p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Pending License Forms</h2>
        {error && <p className="text-red-600">{error}</p>}
        {jobs && pending.length === 0 && <p className="text-gray-600">No applications are waiting for review.</p>}
        {pending.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-gray-200 text-sm text-gray-600">
                  <th className="py-3 font-medium">Applicant</th>
                  <th className="py-3 font-medium">Submitted</th>
                  <th className="py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pending.map((job) => (
                  <tr key={job.id} className="border-b border-gray-100">
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2 text-gray-900 font-medium">
                        <User size={16} />
                        {job.applicant}
                      </div>
                      <div className="flex items-center gap-2 text-gray-500 text-sm mt-1">
                        <Mail size={14} />
                        {job.email}
                      </div>
                    </td>
                    <td className="py-3 text-gray-700">
                      <span className="inline-flex items-center gap-1">
                        <Clock size={14} className="text-gray-500" />
                        {new Date(job.updated_at).toLocaleDateString()}
                      </span>
                    </td>
                    <td className="py-3">
                      <div className="flex gap-2">
                        <a
                          href={`/api/backend/admin/jobs/${job.id}/pdf`}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 border border-gray-300 px-3 py-1 rounded-md hover:bg-gray-100"
                        >
                          <FileText size={16} /> View
                        </a>
                        <button
                          onClick={() => decide(job, "rejected")}
                          className="inline-flex items-center gap-1 bg-red-50 text-red-600 border border-red-200 px-3 py-1 rounded-md hover:bg-red-100"
                        >
                          <X size={16} /> Reject
                        </button>
                        <button
                          onClick={() => decide(job, "approved")}
                          className="inline-flex items-center gap-1 bg-green-600 text-white px-3 py-1 rounded-md hover:bg-green-700"
                        >
                          <Check size={16} /> Send Forward
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

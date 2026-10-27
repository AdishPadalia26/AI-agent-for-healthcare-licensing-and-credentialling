"use client";

import { FileText } from "lucide-react";

export default function HistoryPage() {
  const forms = [
    {
      title: "Medical License Form 1",
      description:
        "Complete onboarding documentation for new employees including personal details, emergency contacts, and license information.",
      updated: "Oct 10, 2025",
      status: "Completed",
      progress: 100,
    },
    {
      title: "Medical License Form 2",
      description:
        "Complete onboarding documentation for new employees including personal details, emergency contacts, and license information.",
      updated: "Oct 11, 2025",
      status: "Incomplete",
      progress: 65,
    },
    {
      title: "Medical License Form 3",
      description:
        "Complete onboarding documentation for new employees including personal details, emergency contacts, and license information.",
      updated: "Oct 8, 2025",
      status: "Completed",
      progress: 100,
    },
    {
      title: "Medical License Form 4",
      description:
        "Complete onboarding documentation for new employees including personal details, emergency contacts, and license information.",
      updated: "Oct 9, 2025",
      status: "Incomplete",
      progress: 30,
    },
    {
      title: "Medical License Form 5",
      description:
        "Complete onboarding documentation for new employees including personal details, emergency contacts, and license information.",
      updated: "Oct 5, 2025",
      status: "Completed",
      progress: 100,
    },
    
  ];

  const completedCount = forms.filter((f) => f.status === "Completed").length;
  const incompleteCount = forms.length - completedCount;

  return (
    <div className="min-h-screen w-full bg-gray-50 px-6 py-10 flex flex-col items-center">
      {/* Header */}
      <div className="max-w-6xl w-full mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-gray-300 text-gray-800 p-2 rounded-full">
            <FileText size={24} />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Form History</h1>
        </div>
        <p className="text-gray-700">
          View and manage all your submitted and in-progress forms
        </p>
        <div className="flex gap-6 mt-3 text-sm font-medium">
          <span className="text-gray-900">
            Total Forms: <span className="font-bold">{forms.length}</span>
          </span>
          <span className="text-green-700">
            Completed: <span className="font-bold">{completedCount}</span>
          </span>
          <span className="text-amber-700">
            Incomplete: <span className="font-bold">{incompleteCount}</span>
          </span>
        </div>
      </div>

      {/* Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl w-full">
        {forms.map((form, idx) => (
          <div
            key={idx}
            className="bg-white rounded-lg shadow-md p-6 flex flex-col justify-between hover:shadow-lg transition"
          >
            {/* Title & Status */}
            <div className="flex items-start justify-between mb-3">
              <h2 className="text-lg font-semibold text-gray-900 pr-2">
                {form.title}
              </h2>
              <span
                className={`text-xs px-2 py-1 rounded-full font-semibold ${
                  form.status === "Completed"
                    ? "bg-green-200 text-green-800"
                    : "bg-amber-200 text-amber-800"
                }`}
              >
                {form.status}
              </span>
            </div>

            {/* Description */}
            <p className="text-gray-700 text-sm mb-4">{form.description}</p>

            {/* Progress bar for incomplete */}
            {form.status === "Incomplete" && (
              <div className="mb-3">
                <div className="flex justify-between text-xs mb-1 text-gray-800 font-medium">
                  <span>Progress</span>
                  <span>{form.progress}%</span>
                </div>
                <div className="w-full bg-gray-200 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-black h-2"
                    style={{ width: `${form.progress}%` }}
                  ></div>
                </div>
              </div>
            )}

            {/* Last updated */}
            <p className="text-gray-600 text-xs mb-4">
              Last updated: {form.updated}
            </p>

            {/* Actions */}
            {form.status === "Completed" ? (
              <div className="flex gap-2">
                <button className="flex-1 border border-gray-400 text-gray-800 rounded-md py-2 text-sm hover:bg-gray-100">
                  View
                </button>
                <button className="flex-1 bg-black text-white rounded-md py-2 text-sm hover:bg-gray-800">
                  Download
                </button>
              </div>
            ) : (
              <div className="flex gap-2">
                <button className="flex-1 border border-gray-400 text-gray-800 rounded-md py-2 text-sm hover:bg-gray-100">
                  Save & Exit
                </button>
                <button className="flex-1 bg-black text-white rounded-md py-2 text-sm hover:bg-gray-800">
                  Save & Submit
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

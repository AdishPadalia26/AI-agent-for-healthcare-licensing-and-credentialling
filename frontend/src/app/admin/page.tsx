"use client";

import { Check, Clock, Mail, User, X } from "lucide-react";

export default function AdminDashboardPage() {
  const applications = [
    {
      name: "John Smith",
      email: "john.smith@example.com",
      submitted: "2 days ago",
      status: "Pending Review",
    },
    {
      name: "Sarah Johnson",
      email: "sarah.j@example.com",
      submitted: "5 days ago",
      status: "Pending Review",
    },
    {
      name: "Michael Chen",
      email: "mchen@example.com",
      submitted: "1 day ago",
      status: "Pending Review",
    },
    {
      name: "Emily Davis",
      email: "emily.davis@example.com",
      submitted: "7 days ago",
      status: "Pending Review",
    },
    {
      name: "Robert Wilson",
      email: "r.wilson@example.com",
      submitted: "3 days ago",
      status: "Pending Review",
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center px-4 py-10">
      {/* Dashboard Header */}
      <div className="max-w-4xl w-full mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-blue-100 text-blue-600 p-2 rounded-full">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="w-6 h-6"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 11c0 .94-.218 1.826-.606 2.607a7.48 7.48 0 01-1.893 2.393L12 21l2.5-5a7.48 7.48 0 01-1.893-2.393A5.978 5.978 0 0012 11zm0-7a4 4 0 110 8 4 4 0 010-8z"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
        </div>
        <p className="text-gray-600">
          Review and manage practitioner license form applications
        </p>
      </div>

      {/* Pending Forms Table */}
      <div className="bg-white rounded-lg shadow-lg max-w-4xl w-full p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">
          Pending License Forms
        </h2>
        <p className="text-gray-600 mb-4">
          Review and process practitioner license applications
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-gray-200 text-sm text-gray-600">
                <th className="py-3 font-medium">Applicant</th>
                <th className="py-3 font-medium">Submitted</th>
                <th className="py-3 font-medium">Status</th>
                <th className="py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {applications.map((app, index) => (
                <tr
                  key={index}
                  className="border-b border-gray-100 hover:bg-gray-50"
                >
                  <td className="py-3 pr-4">
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2 text-gray-900 font-medium">
                        <User size={16} />
                        {app.name}
                      </div>
                      <div className="flex items-center gap-2 text-gray-500 text-sm mt-1">
                        <Mail size={14} />
                        {app.email}
                      </div>
                    </div>
                  </td>
                  <td className="py-3 text-gray-700 flex items-center gap-1">
                    <Clock size={14} className="text-gray-500" />
                    {app.submitted}
                  </td>
                  <td className="py-3">
                    <span className="inline-flex items-center rounded-full bg-gray-200 px-3 py-1 text-sm font-medium text-gray-700">
                      {app.status}
                    </span>
                  </td>
                  <td className="py-3">
                    <div className="flex gap-2">
                      <button className="inline-flex items-center gap-1 bg-red-50 text-red-600 border border-red-200 px-3 py-1 rounded-md hover:bg-red-100 transition">
                        <X size={16} />
                        Reject
                      </button>
                      <button className="inline-flex items-center gap-1 bg-green-600 text-white px-3 py-1 rounded-md hover:bg-green-700 transition">
                        <Check size={16} />
                        Send Forward
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

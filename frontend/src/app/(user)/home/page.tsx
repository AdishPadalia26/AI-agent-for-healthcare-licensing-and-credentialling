"use client";

import { FileText, Upload } from "lucide-react";
import Link from "next/link";

export default function HomePage() {
  return (
    <div className="min-h-screen w-full bg-gradient-to-b from-indigo-50 to-white flex flex-col items-center px-4 py-16">
      {/* Header Section */}
      <div className="text-center mb-12">
        <div className="flex justify-center mb-4">
          <div className="p-4 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-2xl text-white">
            <FileText size={40} />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Application Portal
        </h1>
        <p className="text-gray-600 max-w-xl mx-auto">
          Welcome to our application portal. Choose an option below to get
          started with your submission.
        </p>
      </div>

      {/* Cards Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl w-full">
        {/* Upload CV Card */}
        <div className="bg-white rounded-xl shadow-md p-8 hover:shadow-lg transition">
          <div className="flex justify-center mb-4">
            <div className="p-4 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-2xl text-white">
              <Upload size={36} />
            </div>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 text-center mb-2">
            Upload CV
          </h2>
          <p className="text-gray-600 text-center mb-4">
            Submit your resume and application details
          </p>
          <ul className="text-gray-700 mb-6 space-y-2">
            <li className="flex items-center gap-2">
              <span className="text-blue-500">•</span> Upload your CV in PDF
              format
            </li>
            <li className="flex items-center gap-2">
              <span className="text-blue-500">•</span> Fill out application
              information
            </li>
            <li className="flex items-center gap-2">
              <span className="text-blue-500">•</span> Quick and easy process
            </li>
          </ul>
          <div className="text-center">
            <Link
              href="/upload"
              className="text-blue-600 font-medium inline-flex items-center gap-1 hover:text-blue-800 transition"
            >
              Get Started →
            </Link>
          </div>
        </div>

        {/* Upload License Form Card */}
        <div className="bg-white rounded-xl shadow-md p-8 hover:shadow-lg transition">
          <div className="flex justify-center mb-4">
            <div className="p-4 bg-gradient-to-r from-pink-500 to-purple-600 rounded-2xl text-white">
              <FileText size={36} />
            </div>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 text-center mb-2">
            Form History
          </h2>
          <p className="text-gray-600 text-center mb-4">
            See your form History
          </p>
          <ul className="text-gray-700 mb-6 space-y-2">
            <li className="flex items-center gap-2">
              <span className="text-pink-500">•</span> Form History
            </li>
            <li className="flex items-center gap-2">
              <span className="text-pink-500">•</span> Track application status
            </li>
            <li className="flex items-center gap-2">
              <span className="text-pink-500">•</span> Secure and confidential
            </li>
          </ul>
          <div className="text-center">
            <Link
              href="/history"
              className="text-pink-600 font-medium inline-flex items-center gap-1 hover:text-pink-800 transition"
            >
              Get Started →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

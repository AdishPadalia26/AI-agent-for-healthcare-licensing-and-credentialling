"use client";

import { CheckCircle2, Clock, Brain } from "lucide-react";
import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col items-center bg-white text-gray-900">
      {/* Hero Section */}
      <section className="flex flex-col items-center text-center px-6 py-20">
        {/* Logo */}
        <div className="flex flex-col items-center mb-6">
          <div className="p-3 bg-blue-50 text-blue-600 rounded-2xl mb-2">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="#2563eb"
              className="w-8 h-8"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 13h3l2-5 3 9 2-4h5"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21 13a9 9 0 1 0-18 0 9 9 0 0 0 18 0z"
              />
            </svg>
          </div>
          <span className="text-xl font-semibold text-gray-800">FormAI</span>
        </div>

        {/* Headline */}
        <h1 className="text-2xl sm:text-3xl font-semibold mb-4">
          Automate Healthcare Licensing & Credentialing in Minutes
        </h1>
        <p className="text-gray-600 max-w-2xl mb-8">
          No more repetitive data entry. Our AI agent fills out complex
          licensing and credentialing forms automatically—fast, accurate, and
          secure.
        </p>

        {/* Buttons */}
        <div className="flex gap-4">
          <Link
            href="/login"
            className="bg-blue-600 text-white font-medium px-6 py-2 rounded-md hover:bg-blue-700 transition"
          >
            Login
          </Link>
          <Link
            href="/signup"
            className="border border-blue-600 text-blue-600 font-medium px-6 py-2 rounded-md hover:bg-blue-50 transition"
          >
            Sign Up
          </Link>
        </div>
      </section>

      {/* Features Section */}
      <section className="w-full bg-gray-50 py-16 px-6">
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
          {/* Feature 1 */}
          <div className="flex flex-col items-center">
            <div className="p-4 bg-blue-50 text-blue-600 rounded-2xl mb-4">
              <Clock size={32} />
            </div>
            <h2 className="text-lg font-semibold mb-2">Save Time</h2>
            <p className="text-gray-600 text-sm max-w-xs">
              Automate form filling across state licensing, hospital
              credentialing, and payer enrollment.
            </p>
          </div>

          {/* Feature 2 */}
          <div className="flex flex-col items-center">
            <div className="p-4 bg-blue-50 text-blue-600 rounded-2xl mb-4">
              <Brain size={32} />
            </div>
            <h2 className="text-lg font-semibold mb-2">AI-Driven</h2>
            <p className="text-gray-600 text-sm max-w-xs">
              Extracts and maps provider data to the correct fields with zero
              manual effort.
            </p>
          </div>

          {/* Feature 3 */}
          <div className="flex flex-col items-center">
            <div className="p-4 bg-blue-50 text-blue-600 rounded-2xl mb-4">
              <CheckCircle2 size={32} />
            </div>
            <h2 className="text-lg font-semibold mb-2">
              Accuracy & Compliance
            </h2>
            <p className="text-gray-600 text-sm max-w-xs">
              Built to ensure error-free, regulation-aligned submissions.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

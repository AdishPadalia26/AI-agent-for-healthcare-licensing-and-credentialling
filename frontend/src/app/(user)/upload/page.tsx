"use client"

import React, { useEffect, useState } from 'react'
import dynamic from "next/dynamic";
import { AnimatePresence, motion } from "motion/react";

const PDFViewer = dynamic(
  async () => {
    const pdf = await import("react-pdf");
    const { Document, Page, pdfjs } = pdf;
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      "pdfjs-dist/build/pdf.worker.min.mjs",
      import.meta.url
    ).toString();
    return ({ file, pageNumber, onLoadSuccess }: any) => (
      <Document file={file} onLoadSuccess={onLoadSuccess}>
        <Page pageNumber={pageNumber} />
      </Document>
    );
  },
  { ssr: false } // ⛔ prevents prerendering (fixes DOMMatrix issue)
);

import "react-pdf/dist/Page/AnnotationLayer.css"; // Optional: for annotations
import "react-pdf/dist/Page/TextLayer.css";

type Props = {}

interface DocumentLoadSuccess {
  numPages: number;
}

const Upload = (props: Props) => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [isContentVisible, setIsContentVisible] = useState(false);
  const [mainFile, setMainFile] = useState<File | null>(null);
  const [formFile, setFormFile] = useState<File | null>(null);
  const [supportUrl, setSupportUrl] = useState('');
  const [isVisible, setIsVisible] = useState(true);
  const [urlStatus, setUrlStatus] = useState<'pending' | 'success' | 'error' | null>(null);
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState(1);
  
  function onDocumentLoadSuccess({ numPages }: DocumentLoadSuccess) {
    setNumPages(numPages);
  }
  const checkUrl = () => {
    if (!supportUrl.trim()) {
      setUrlStatus('error');
      return;
    }

    setUrlStatus('pending');
    const isSuccess = supportUrl.includes('valid') || supportUrl.includes('license');

    setTimeout(() => {
      setUrlStatus(isSuccess ? 'success' : 'error');
    }, 1000);
  };
  
  const renderUrlStatus = () => {
    if (urlStatus === "pending") {
      return (
        <p className="text-xs mt-1 text-gray-500">
          Checking URL reachability...
        </p>
      );
    } else if (urlStatus === "success") {
      return (
        <p className="text-xs mt-1 text-green-600">
          URL is reachable and appears valid.
        </p>
      );
    } else if (urlStatus === "error") {
      return (
        <p className="text-xs mt-1 text-red-600">
          URL check failed (CORS/404 simulated). Proceeding without it.
        </p>
      );
    }
    return <p id="status-url" className="text-xs mt-1 text-gray-500"></p>;
  };

  const handleClick = () => {
    // Start AI processing
    setIsProcessing(true);
    setIsContentVisible(false);

    // After 10 seconds, show extraction complete
    setTimeout(() => {
      setIsProcessing(false);
      setIsContentVisible(true);
      setIsVisible(!isVisible);
    }, 10000); // 10 seconds
  };


  return (
    <div className="w-full">
      <AnimatePresence mode="wait" initial={false}>
        {isVisible ? (
          <motion.div
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0 }}
            key="upload"
            className="flex flex-col justify-center items-center w-full min-h-screen"
          >
            <h1 className="text-3xl mb-4 font-semibold">
              Good Afternoon, <span className="text-orange-600">Mihir</span>
            </h1>
            <h1 className="text-2xl">
              Automate Healthcare Licensing & Credentialing in Minutes
            </h1>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 pt-4 w-[60vw] mt-12">
              <div>
                <label className="block text-lg font-medium text-gray-700 mb-2">
                  1. Provider Document (e.g., CV)
                </label>
                <input
                  type="file"
                  id="upload-main"
                  accept=".pdf,.jpg,.png"
                  onChange={(e) =>
                    setMainFile(e.target.files ? e.target.files[0] : null)
                  }
                  className="w-full cursor-pointer text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-10"
                />
                <p id="status-main" className="text-xs mt-1 text-gray-500">
                  {mainFile
                    ? `Selected: ${mainFile.name}`
                    : "No file selected."}
                </p>
              </div>
              <div>
                <label className="block text-lg font-medium text-gray-700 mb-2">
                  2. Form
                </label>
                <input
                  type="file"
                  id="upload-support"
                  accept=".pdf,.jpg,.png"
                  onChange={(e) =>
                    setFormFile(e.target.files ? e.target.files[0] : null)
                  }
                  className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-green-50 file:text-green-700 hover:file:bg-green-10"
                />

                <div className="mt-3">
                  <label
                    htmlFor="support-url"
                    className="block text-xs font-medium text-gray-500 mb-1"
                  >
                    ... or enter URL (Optional)
                  </label>
                  <div className="flex space-x-2">
                    <input
                      type="url"
                      id="support-url"
                      placeholder="https://external-license-site.com"
                      value={supportUrl}
                      onChange={(e) => setSupportUrl(e.target.value)}
                      className={`p-2 border rounded-lg w-full text-sm focus:ring-green-500 ${
                        urlStatus === "error"
                          ? "border-red-500"
                          : "border-gray-300 focus:border-green-500"
                      }`}
                    />
                    <button
                      onClick={checkUrl}
                      disabled={isProcessing}
                      className="bg-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-sm hover:bg-gray-300 transition-colors disabled:opacity-50"
                    >
                      {urlStatus === "pending" ? "..." : "Check"}
                    </button>
                  </div>
                  {renderUrlStatus()}
                </div>
              </div>
            </div>
            <div className="flex justify-center pt-4">
              <button
                onClick={() => handleClick()}
                id="process-btn"
                disabled={isProcessing}
                className={`px-8 py-3 mt-12 font-bold rounded-xl shadow-lg transition-transform transform hover:scale-[1.01] disabled:bg-gray-400 ${
                  isProcessing
                    ? "bg-orange-500"
                    : isContentVisible
                    ? "bg-green-600"
                    : "bg-orange-300 hover:bg-orange-500"
                }`}
              >
                {isProcessing
                  ? "🤖 AI Processing..."
                  : isContentVisible
                  ? "✅ Extraction Complete"
                  : "Start AI Extraction"}
              </button>
            </div>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0 }}
            key="form"
            className="flex flex-col justify-center items-center w-full h-screen"
          >
            <div className="bg-white rounded-lg shadow-lg w-full grid grid-cols-12 h-screen">
              <div className="col-span-8 px-12 py-8 overflow-auto border-r-1">
                <div className="flex justify-between mb-3">
                  <h1 className="text-3xl font-semibold">Filled Form</h1>
                  <div className="flex justify-between gap-4">
                    <button
                      onClick={() => setIsVisible(!isVisible)}
                      className="bg-red-300 hover:bg-red-500 py-2 px-4 rounded-xl transition"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={1.5}
                        stroke="currentColor"
                        className="size-6"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M9 15 3 9m0 0 6-6M3 9h12a6 6 0 0 1 0 12h-3"
                        />
                      </svg>
                    </button>
                    <a
                      href="/filled_form.pdf"
                      className="bg-blue-300 hover:bg-blue-500 py-2 px-4 rounded-xl transition"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={1.5}
                        stroke="currentColor"
                        className="size-6"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
                        />
                      </svg>
                    </a>
                  </div>
                </div>
                {mainFile && formFile && (
                  <PDFViewer
                    file="/filled_form.pdf"
                    pageNumber={pageNumber}
                    onLoadSuccess={onDocumentLoadSuccess}
                  />
                )}
                <div className="flex flex-col w-full justify-center items-center">
                  <p className="text-sm my-2">
                    Page {pageNumber} of {numPages}
                  </p>
                  <div className="flex gap-4">
                    <button
                      onClick={() =>
                        setPageNumber((prevPage) => Math.max(prevPage - 1, 1))
                      }
                      className="p-2 bg-gray-200 rounded-full hover:bg-gray-300"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={1.5}
                        stroke="currentColor"
                        className="size-6"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M15.75 19.5 8.25 12l7.5-7.5"
                        />
                      </svg>
                    </button>
                    <button
                      onClick={() =>
                        setPageNumber((prevPage) =>
                          Math.min(prevPage + 1, numPages)
                        )
                      }
                      className="p-2 bg-gray-200 rounded-full hover:bg-gray-300"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={1.5}
                        stroke="currentColor"
                        className="size-6"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="m8.25 4.5 7.5 7.5-7.5 7.5"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
              <div className="p-8 col-span-4 overflow-auto">
                <h2 className="text-xl font-semibold text-gray-800 mb-2">
                  Incomplete Details
                </h2>
                <p className="text-gray-600 mb-6">
                  Fill in your information to complete your application.
                </p>

                <form className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-800">
                      Secondary Office Address
                    </label>
                    <input
                      type="text"
                      className="mt-1 block w-full rounded-md border border-gray-400 px-3 py-2 text-gray-900 placeholder-gray-500 focus:ring-2 focus:ring-black focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-800">
                      Date Taken
                    </label>
                    <input
                      type="text"
                      className="mt-1 block w-full rounded-md border border-gray-400 px-3 py-2 text-gray-900 placeholder-gray-500 focus:ring-2 focus:ring-black focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-800">
                      USMLE No.
                    </label>
                    <input
                      type="text"
                      className="mt-1 block w-full rounded-md border border-gray-400 px-3 py-2 text-gray-900 placeholder-gray-500 focus:ring-2 focus:ring-black focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-800">
                      National Board of Medical Examiners
                    </label>
                    <input
                      type="text"
                      className="mt-1 block w-full rounded-md border border-gray-400 px-3 py-2 text-gray-900 placeholder-gray-500 focus:ring-2 focus:ring-black focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-800">
                      Internship Type
                    </label>
                    <input
                      type="text"
                      className="mt-1 block w-full rounded-md border border-gray-400 px-3 py-2 text-gray-900 placeholder-gray-500 focus:ring-2 focus:ring-black focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-800">
                      Facility Name
                    </label>
                    <input
                      type="text"
                      className="mt-1 block w-full rounded-md border border-gray-400 px-3 py-2 text-gray-900 placeholder-gray-500 focus:ring-2 focus:ring-black focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-800">
                      Mailing Address
                    </label>
                    <input
                      type="text"
                      className="mt-1 block w-full rounded-md border border-gray-400 px-3 py-2 text-gray-900 placeholder-gray-500 focus:ring-2 focus:ring-black focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-800">
                      Phone
                    </label>
                    <input
                      type="text"
                      className="mt-1 block w-full rounded-md border border-gray-400 px-3 py-2 text-gray-900 placeholder-gray-500 focus:ring-2 focus:ring-black focus:outline-none"
                    />
                  </div>

                  {/* <div>
                    <label className="block text-sm font-medium text-gray-800">
                      Position Applied For
                    </label>
                    <select className="mt-1 block w-full rounded-md border border-gray-400 px-3 py-2 text-gray-900 focus:ring-2 focus:ring-black focus:outline-none">
                      <option>Select a position</option>
                      <option>Cardiologist</option>
                      <option>Surgeon</option>
                      <option>Neurologist</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-800">
                      Years of Experience
                    </label>
                    <select className="mt-1 block w-full rounded-md border border-gray-400 px-3 py-2 text-gray-900 focus:ring-2 focus:ring-black focus:outline-none">
                      <option>Select experience level</option>
                      <option>0-2 years</option>
                      <option>3-5 years</option>
                      <option>6+ years</option>
                    </select>
                  </div> */}

                  {/* <div>
                    <label className="block text-sm font-medium text-gray-800">
                      Cover Letter
                    </label>
                    <textarea
                      placeholder="Tell us why you'd be a great fit for this position..."
                      rows={4}
                      className="mt-1 block w-full rounded-md border border-gray-400 px-3 py-2 text-gray-900 placeholder-gray-500 focus:ring-2 focus:ring-black focus:outline-none"
                    />
                  </div> */}
                  <div className="grid grid-cols-2 gap-4">
                    <button
                      type="submit"
                      className="w-full bg-yellow-300 hover:bg-yellow-500 py-2 rounded-md transition"
                    >
                      Save & Exit
                    </button>
                    <button
                      type="submit"
                      className="w-full bg-green-300 py-2 rounded-md hover:bg-green-500 transition"
                    >
                      Submit
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default Upload;
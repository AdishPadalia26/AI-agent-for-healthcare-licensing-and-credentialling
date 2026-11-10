"use client";

import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { ChevronLeft, ChevronRight } from "lucide-react";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

export default function PdfViewer({ url }: { url: string }) {
  const [pages, setPages] = useState(0);
  const [page, setPage] = useState(1);

  return (
    <div className="flex flex-col items-center">
      <Document
        file={url}
        onLoadSuccess={({ numPages }) => {
          setPages(numPages);
          setPage((current) => Math.min(current, numPages));
        }}
        loading={<p className="p-8 text-gray-500">Loading PDF…</p>}
        error={<p className="p-8 text-red-600">Could not load the PDF.</p>}
      >
        <Page pageNumber={page} renderForms />
      </Document>
      <p className="text-sm my-2">
        Page {page} of {pages}
      </p>
      <div className="flex gap-4">
        <button
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => setPage((p) => p - 1)}
          className="p-2 bg-gray-200 rounded-full hover:bg-gray-300 disabled:opacity-40"
        >
          <ChevronLeft />
        </button>
        <button
          aria-label="Next page"
          disabled={page >= pages}
          onClick={() => setPage((p) => p + 1)}
          className="p-2 bg-gray-200 rounded-full hover:bg-gray-300 disabled:opacity-40"
        >
          <ChevronRight />
        </button>
      </div>
    </div>
  );
}

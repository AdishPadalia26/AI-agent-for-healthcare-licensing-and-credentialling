"use client";

import Link from "next/link";
import { cn } from "@/lib/cn";


import { signIn } from "next-auth/react";    // ✅ for Google sign-in
import { FcGoogle } from "react-icons/fc";  // ✅ Google icon
import React from "react";


type AuthCardProps = {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

export default function AuthCard({ title, subtitle, children, footer }: AuthCardProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="bg-white shadow-xl rounded-2xl border border-slate-200 p-8">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {subtitle ? <p className="text-slate-600 mt-1">{subtitle}</p> : null}
          <div className="mt-6">{children}</div>
        </div>
        {footer ? (
          <div className="text-center text-sm text-slate-600 mt-4">{footer}</div>
        ) : null}
      </div>
    </div>
  );
}

export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent",
        className
      )}
      {...props}
    />
  );
}

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn("mb-1 block text-sm font-medium text-slate-700", className)}
      {...props}
    />
  );
}

export function Button({
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-white font-medium shadow-sm hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-50 disabled:cursor-not-allowed transition",
        className
      )}
      {...props}
    />
  );
}

export function Divider({ text = "or" }: { text?: string }) {
  return (
    <div className="relative my-6">
      <div className="absolute inset-0 flex items-center" aria-hidden="true">
        <div className="w-full border-t border-slate-200" />
      </div>
      <div className="relative flex justify-center">
        <span className="bg-white px-2 text-xs uppercase tracking-wider text-slate-500">
          {text}
        </span>
      </div>
    </div>
  );
}

export function OAuthRow() {
  return (
    <div className="grid grid-cols-1 gap-3">
      <button
        type="button"
        onClick={() => signIn("google", { callbackUrl: "/" })}
        className="flex items-center justify-center gap-2 w-full rounded-lg border border-gray-300 bg-white py-2 text-gray-700 hover:bg-gray-50 hover:border-gray-400 transition"
      >
        <FcGoogle className="text-xl" />
        Continue with Google
      </button>
    </div>
  );
}


"use client";

import AuthCard, { Button, Divider, Input, Label, OAuthRow } from "@/components/auth/AuthCard";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter()
  const [form, setForm] = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error("Invalid credentials");
      alert(`Login success: ${form.email}`);
      router.push('/home')
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-indigo-100 px-4">
      <div className="w-full max-w-md">
        <div className="bg-white shadow-2xl rounded-2xl border border-gray-200 p-8 space-y-6">
          <div className="text-center space-y-1">
            <h1 className="text-3xl font-bold text-gray-900">Welcome back</h1>
            <p className="text-gray-500">Login to your account</p>
          </div>

          <form onSubmit={onSubmit} className="space-y-5">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                placeholder="you@example.com"
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                placeholder="••••••••"
                type="password"
                required
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              />
            </div>
            {error && <p className="text-red-600 text-sm">{error}</p>}

            <Button
              type="submit"
              disabled={loading}
              className="w-full text-lg py-2.5 bg-indigo-600 hover:bg-indigo-700"
            >
              {loading ? "Signing in..." : "Sign in"}
            </Button>

            <Divider text="OR" />

            <OAuthRow />
          </form>

          <div className="text-center text-sm text-gray-600">
            Don’t have an account?{" "}
            <Link href="/signup" className="text-indigo-600 hover:underline font-medium">
              Sign up
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

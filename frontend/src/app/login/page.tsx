"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (submitting) return;

    setSubmitting(true);
    setError("");

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          password,
        }),
      });

      const body = (await response.json()) as {
        authenticated?: boolean;
        detail?: string;
      };

      if (!response.ok || !body.authenticated) {
        throw new Error(
          body.detail || "تعذر تسجيل الدخول",
        );
      }

      router.replace("/tickets");
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "تعذر تسجيل الدخول",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main
      dir="rtl"
      className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#050914] px-4 text-white"
    >
      <div className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-cyan-500/15 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 -left-32 h-[28rem] w-[28rem] rounded-full bg-blue-600/15 blur-3xl" />

      <section className="relative w-full max-w-md rounded-3xl border border-white/10 bg-white/[0.05] p-6 shadow-2xl shadow-black/40 backdrop-blur-xl sm:p-8">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-400 to-blue-600 text-xl font-black text-slate-950 shadow-lg shadow-cyan-950/50">
            TX
          </div>

          <p className="text-sm font-medium text-cyan-400">
            Travel-X Operations
          </p>

          <h1 className="mt-2 text-2xl font-bold">
            تسجيل دخول الموظفين
          </h1>

          <p className="mt-3 text-sm leading-6 text-slate-400">
            هذه المنطقة مخصصة لعرض تذاكر الأقسام المصرح بها.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <label className="block">
            <span className="mb-2 block text-sm text-slate-300">
              اسم المستخدم
            </span>

            <input
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              required
              maxLength={128}
              dir="ltr"
              className="w-full rounded-xl border border-white/10 bg-[#080d1a] px-4 py-3 text-left outline-none transition focus:border-cyan-400/60 focus:ring-4 focus:ring-cyan-400/10"
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm text-slate-300">
              كلمة المرور
            </span>

            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
              maxLength={256}
              dir="ltr"
              className="w-full rounded-xl border border-white/10 bg-[#080d1a] px-4 py-3 text-left outline-none transition focus:border-cyan-400/60 focus:ring-4 focus:ring-cyan-400/10"
            />
          </label>

          {error && (
            <div
              role="alert"
              className="rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-200"
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-gradient-to-l from-cyan-400 to-blue-500 px-5 py-3.5 font-bold text-slate-950 transition hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "جارٍ التحقق..." : "تسجيل الدخول"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-600">
          الجلسة محمية وتنتهي تلقائيًا بعد ثماني ساعات.
        </p>
      </section>
    </main>
  );
}
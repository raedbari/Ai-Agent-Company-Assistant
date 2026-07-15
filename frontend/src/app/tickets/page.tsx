"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

type Department = "txsaas" | "cybtx" | "destination";

type AuditEvent = {
  event_id: string;
  event_type: string;
  actor_type: string;
  session_id: string;
  draft_version: number;
  occurred_at: string;
};

type Ticket = {
  ticket_id: string;
  ticket_number: string;
  status: string;
  source_session_id: string;
  source_draft_id: string;
  source_draft_version: number;
  service_key: string;
  assigned_department: Department;
  requirements: Record<string, string>;
  additional_features: string[];
  customer_notes: string[];
  audit_events: AuditEvent[];
  created_at: string;
};

type TicketsResponse = {
  department: Department;
  tickets: Ticket[];
  detail?: string;
};

const departments: Array<{
  key: Department;
  name: string;
  description: string;
}> = [
  {
    key: "txsaas",
    name: "TXSaaS",
    description: "المواقع والتطبيقات والأنظمة البرمجية",
  },
  {
    key: "cybtx",
    name: "CYBTX",
    description: "الاستضافة والحماية والأمن السيبراني",
  },
  {
    key: "destination",
    name: "Destination",
    description: "التسويق والتصميم والهوية البصرية",
  },
];

const requirementLabels: Record<string, string> = {
  business_type: "مجال النشاط",
  website_goal: "هدف الموقع",
  existing_website: "وجود موقع حالي",
  features: "المزايا المطلوبة",
  languages: "اللغات",
  website_type: "نوع الموقع",
  expected_traffic: "الزيارات المتوقعة",
  domain_status: "حالة النطاق",
  backup_needed: "النسخ الاحتياطي",
  security_needed: "الحماية الأمنية",
  project_name: "اسم المشروع",
  target_audience: "الجمهور المستهدف",
  preferred_style: "النمط المفضل",
  preferred_colors: "الألوان المفضلة",
};

function formatDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ar", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatValue(value: string) {
  if (value === "yes") return "نعم";
  if (value === "no") return "لا";
  return value;
}

export default function TicketsPage() {
  const [department, setDepartment] =
    useState<Department>("txsaas");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [loggingOut, setLoggingOut] = useState(false);

async function handleLogout() {
  if (loggingOut) return;

  setLoggingOut(true);

  try {
    const response = await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error("Logout failed");
    }

    window.location.replace("/login");
  } catch {
    setError("تعذر تسجيل الخروج، حاول مرة أخرى.");
    setLoggingOut(false);
  }
}

  const loadTickets = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `/api/departments/${department}/tickets?limit=100`,
        { cache: "no-store" },
      );

      const body = (await response.json()) as TicketsResponse;

      if (!response.ok) {
        throw new Error(body.detail || "تعذر تحميل التذاكر");
      }

      const receivedTickets = Array.isArray(body.tickets)
        ? body.tickets
        : [];

      setTickets(receivedTickets);
      setSelectedId((currentId) => {
        const currentExists = receivedTickets.some(
          (ticket) => ticket.ticket_id === currentId,
        );

        return currentExists
          ? currentId
          : receivedTickets[0]?.ticket_id ?? null;
      });
    } catch (reason) {
      setTickets([]);
      setSelectedId(null);
      setError(
        reason instanceof Error
          ? reason.message
          : "حدث خطأ أثناء تحميل التذاكر",
      );
    } finally {
      setLoading(false);
    }
  }, [department]);

  useEffect(() => {
    void loadTickets();
  }, [loadTickets]);

  const filteredTickets = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("ar");

    if (!query) return tickets;

    return tickets.filter((ticket) => {
      const searchableText = [
        ticket.ticket_number,
        ticket.service_key,
        ticket.source_session_id,
        ...Object.values(ticket.requirements),
        ...ticket.additional_features,
      ]
        .join(" ")
        .toLocaleLowerCase("ar");

      return searchableText.includes(query);
    });
  }, [search, tickets]);

  const selectedTicket =
    filteredTickets.find((ticket) => ticket.ticket_id === selectedId) ??
    filteredTickets[0] ??
    null;

  const currentDepartment = departments.find(
    (item) => item.key === department,
  );

  return (
    <main
      dir="rtl"
      className="relative min-h-screen overflow-hidden bg-[#050914] text-white"
    >
      <div className="pointer-events-none fixed -right-40 -top-40 h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl" />
      <div className="pointer-events-none fixed -bottom-48 -left-40 h-[32rem] w-[32rem] rounded-full bg-blue-600/10 blur-3xl" />

      <div className="relative mx-auto max-w-[1500px] px-4 py-6 sm:px-6 lg:px-8">
        <header className="mb-6 flex flex-col gap-4 rounded-3xl border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl sm:flex-row sm:items-center sm:justify-between">
  <div>
    <p className="mb-2 text-sm font-medium text-cyan-400">
      Travel-X Operations
    </p>

    <h1 className="text-2xl font-bold sm:text-3xl">
      لوحة إدارة التذاكر
    </h1>

    <p className="mt-2 text-sm text-slate-400">
      عرض التذاكر المحفوظة وتفاصيلها حسب القسم المسؤول.
    </p>
  </div>

  <div className="flex flex-wrap gap-3">
    <button
      type="button"
      onClick={() => void loadTickets()}
      disabled={loading}
      className="rounded-xl border border-white/10 bg-white/[0.05] px-4 py-3 text-sm transition hover:border-cyan-400/40 hover:bg-cyan-400/10 disabled:opacity-50"
    >
      {loading ? "جارٍ التحديث..." : "تحديث البيانات"}
    </button>

    <Link
      href="/"
      className="rounded-xl bg-gradient-to-l from-cyan-400 to-blue-500 px-5 py-3 text-sm font-bold text-slate-950 transition hover:scale-[1.03]"
    >
      العودة للمحادثة
    </Link>

    <button
      type="button"
      onClick={handleLogout}
      disabled={loggingOut}
      className="rounded-xl border border-red-400/25 bg-red-400/10 px-5 py-3 text-sm font-bold text-red-200 transition hover:bg-red-400/20 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {loggingOut
        ? "جارٍ تسجيل الخروج..."
        : "تسجيل الخروج"}
    </button>
  </div>
</header>

<section className="mb-6 grid gap-3 md:grid-cols-3">
  {departments.map((item) => {
    const active = department === item.key;

    return (
      <button
        key={item.key}
        type="button"
        onClick={() => {
          setDepartment(item.key);
          setSearch("");
          setSelectedId(null);
        }}
        className={`rounded-2xl border p-4 text-right transition-all duration-300 ${
          active
            ? "border-cyan-400/50 bg-cyan-400/10 shadow-lg shadow-cyan-950/30"
            : "border-white/10 bg-white/[0.03] hover:-translate-y-1 hover:border-white/20"
        }`}
      >
        <div className="flex items-center justify-between">
          <strong className="text-lg">{item.name}</strong>

          {active && (
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-cyan-400" />
          )}
        </div>

        <p className="mt-2 text-sm text-slate-400">
          {item.description}
        </p>
      </button>
    );
  })}
</section>

        <section className="mb-6 grid gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
            <p className="text-sm text-slate-400">القسم الحالي</p>
            <p className="mt-2 text-xl font-bold text-cyan-300">
              {currentDepartment?.name}
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
            <p className="text-sm text-slate-400">إجمالي التذاكر</p>
            <p className="mt-2 text-2xl font-bold">{tickets.length}</p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
            <p className="text-sm text-slate-400">التذاكر الجديدة</p>
            <p className="mt-2 text-2xl font-bold text-emerald-400">
              {tickets.filter((ticket) => ticket.status === "new").length}
            </p>
          </div>
        </section>

        <section className="grid min-h-[650px] gap-5 lg:grid-cols-[minmax(340px,0.85fr)_minmax(0,1.35fr)]">
          <aside className="rounded-3xl border border-white/10 bg-white/[0.035] p-4 backdrop-blur-xl">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="ابحث برقم التذكرة أو الخدمة..."
              className="mb-4 w-full rounded-xl border border-white/10 bg-[#080d1a] px-4 py-3 text-sm outline-none transition placeholder:text-slate-600 focus:border-cyan-400/50"
            />

            <div className="max-h-[570px] space-y-3 overflow-y-auto pl-1">
              {loading &&
                Array.from({ length: 4 }).map((_, index) => (
                  <div
                    key={index}
                    className="h-28 animate-pulse rounded-2xl bg-white/[0.05]"
                  />
                ))}

              {!loading && error && (
                <div className="rounded-2xl border border-red-400/20 bg-red-400/10 p-5 text-sm text-red-200">
                  <p>{error}</p>
                  <p className="mt-2 text-red-300/70">
                    تأكد من تشغيل FastAPI على المنفذ 8000.
                  </p>
                </div>
              )}

              {!loading &&
                !error &&
                filteredTickets.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center text-sm text-slate-500">
                    لا توجد تذاكر مطابقة في هذا القسم.
                  </div>
                )}

              {!loading &&
                !error &&
                filteredTickets.map((ticket, index) => {
                  const active =
                    selectedTicket?.ticket_id === ticket.ticket_id;

                  return (
                    <button
                      key={ticket.ticket_id}
                      type="button"
                      onClick={() => setSelectedId(ticket.ticket_id)}
                      style={{ animationDelay: `${index * 60}ms` }}
                      className={`w-full rounded-2xl border p-4 text-right transition-all duration-300 ${
                        active
                          ? "border-cyan-400/50 bg-cyan-400/10"
                          : "border-white/10 bg-[#080d1a]/80 hover:-translate-y-0.5 hover:border-white/20"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <strong className="text-sm text-cyan-200">
                          {ticket.ticket_number}
                        </strong>

                        <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-xs text-emerald-300">
                          {ticket.status === "new"
                            ? "جديدة"
                            : ticket.status}
                        </span>
                      </div>

                      <p className="mt-3 text-sm text-slate-300">
                        {ticket.service_key}
                      </p>

                      <p className="mt-2 text-xs text-slate-500">
                        الإصدار {ticket.source_draft_version} •{" "}
                        {formatDate(ticket.created_at)}
                      </p>
                    </button>
                  );
                })}
            </div>
          </aside>

          <article className="rounded-3xl border border-white/10 bg-white/[0.035] p-5 backdrop-blur-xl sm:p-7">
            {!selectedTicket ? (
              <div className="flex min-h-[500px] items-center justify-center text-slate-500">
                اختر تذكرة لعرض تفاصيلها.
              </div>
            ) : (
              <div className="space-y-7">
                <div className="flex flex-col gap-4 border-b border-white/10 pb-6 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm text-cyan-400">
                      رقم التذكرة
                    </p>
                    <h2 className="mt-2 text-xl font-bold sm:text-2xl">
                      {selectedTicket.ticket_number}
                    </h2>
                    <p className="mt-2 text-sm text-slate-400">
                      أُنشئت في {formatDate(selectedTicket.created_at)}
                    </p>
                  </div>

                  <span className="w-fit rounded-full border border-emerald-400/20 bg-emerald-400/10 px-4 py-2 text-sm text-emerald-300">
                    {selectedTicket.status === "new"
                      ? "تذكرة جديدة"
                      : selectedTicket.status}
                  </span>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-2xl bg-[#080d1a] p-4">
                    <p className="text-xs text-slate-500">القسم</p>
                    <p className="mt-2 font-semibold text-cyan-300">
                      {selectedTicket.assigned_department.toUpperCase()}
                    </p>
                  </div>

                  <div className="rounded-2xl bg-[#080d1a] p-4">
                    <p className="text-xs text-slate-500">الخدمة</p>
                    <p className="mt-2 font-semibold">
                      {selectedTicket.service_key}
                    </p>
                  </div>

                  <div className="rounded-2xl bg-[#080d1a] p-4">
                    <p className="text-xs text-slate-500">إصدار المسودة</p>
                    <p className="mt-2 font-semibold">
                      {selectedTicket.source_draft_version}
                    </p>
                  </div>
                </div>

                <section>
                  <h3 className="mb-4 text-lg font-bold">
                    متطلبات العميل
                  </h3>

                  <div className="grid gap-3 sm:grid-cols-2">
                    {Object.entries(selectedTicket.requirements).map(
                      ([key, value]) => (
                        <div
                          key={key}
                          className="rounded-2xl border border-white/10 bg-[#080d1a] p-4"
                        >
                          <p className="text-xs text-slate-500">
                            {requirementLabels[key] ?? key}
                          </p>
                          <p className="mt-2 text-sm leading-7 text-slate-200">
                            {formatValue(value)}
                          </p>
                        </div>
                      ),
                    )}
                  </div>
                </section>

                <section>
                  <h3 className="mb-4 text-lg font-bold">
                    المزايا الإضافية
                  </h3>

                  {selectedTicket.additional_features.length ? (
                    <div className="flex flex-wrap gap-2">
                      {selectedTicket.additional_features.map(
                        (feature, index) => (
                          <span
                            key={`${feature}-${index}`}
                            className="rounded-xl border border-cyan-400/20 bg-cyan-400/10 px-4 py-2 text-sm text-cyan-200"
                          >
                            {feature}
                          </span>
                        ),
                      )}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">
                      لا توجد مزايا إضافية.
                    </p>
                  )}
                </section>

                <section>
                  <h3 className="mb-4 text-lg font-bold">
                    سجل التذكرة
                  </h3>

                  <div className="space-y-3">
                    {selectedTicket.audit_events.map((event) => (
                      <div
                        key={event.event_id}
                        className="flex flex-col gap-2 rounded-2xl border border-white/10 bg-[#080d1a] p-4 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div>
                          <p className="font-medium">
                            {event.event_type === "created"
                              ? "تم إنشاء التذكرة"
                              : event.event_type}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            بواسطة {event.actor_type} • إصدار{" "}
                            {event.draft_version}
                          </p>
                        </div>

                        <time className="text-xs text-slate-400">
                          {formatDate(event.occurred_at)}
                        </time>
                      </div>
                    ))}
                  </div>
                </section>

                <div className="border-t border-white/10 pt-5">
                  <p className="text-xs text-slate-600">
                    Session: {selectedTicket.source_session_id}
                  </p>
                </div>
              </div>
            )}
          </article>
        </section>
      </div>
    </main>
  );
}
"use client";

import type {
  FormEvent,
  KeyboardEvent,
} from "react";
import {
  useEffect,
  useRef,
  useState,
} from "react";

type MessageRole = "assistant" | "user" | "error";

type ChatMessage = {
  id: string;
  role: MessageRole;
  text: string;
};

type TicketDraft = {
  version: number;
  status: string;
  service_key: string;
  primary_department: string;
  requirements: Record<string, string>;
  additional_features: string[];
  customer_notes: string[];
};

type Ticket = {
  ticket_number: string;
  status: string;
  assigned_department: string;
};

type ChatResponse = {
  session_id: string;
  reply: string;
  stage: string;
  policy_action: string;
  service_key: string | null;
  primary_department: string | null;
  missing_requirements: string[];
  ticket_draft: TicketDraft | null;
  ticket: Ticket | null;
};

const initialMessages: ChatMessage[] = [
  {
    id: "welcome",
    role: "assistant",
    text:
      "مرحبًا بك في Travel-X. أخبرني بالخدمة التي تحتاجها، وسأساعدك في تحديد المتطلبات وإنشاء التذكرة المناسبة.",
  },
];

const quickServices = [
  {
    department: "CYBTX",
    title: "الاستضافة والحماية",
    description: "استضافة، أمن سيبراني، مراقبة ونسخ احتياطي.",
    prompt: "أريد معرفة خدمات الاستضافة والحماية لدى Travel-X",
  },
  {
    department: "TXSaaS",
    title: "تطوير البرمجيات",
    description: "مواقع، تطبيقات، منصات وتكاملات برمجية.",
    prompt: "أريد تطوير موقع أو تطبيق لمشروعي",
  },
  {
    department: "Destination",
    title: "التسويق والتصميم",
    description: "هوية بصرية، شعارات وتصاميم تسويقية.",
    prompt: "أريد معرفة خدمات التصميم والهوية البصرية",
  },
];

const stageLabels: Record<string, string> = {
  new: "محادثة جديدة",
  discovery: "استكشاف الخدمة",
  requirements: "جمع المتطلبات",
  draft_review: "مراجعة المسودة",
  ticket_created: "تم إنشاء التذكرة",
};

const serviceLabels: Record<string, string> = {
  website_development: "تطوير المواقع",
  hosting: "الاستضافة",
  cybersecurity: "الأمن السيبراني",
  visual_identity: "الهوية البصرية",
  logo_design: "تصميم الشعارات",
  mobile_app: "تطوير التطبيقات",
  ai_agent: "وكلاء الذكاء الاصطناعي",
};

function createId() {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random()}`;
}

export default function Home() {
  const [messages, setMessages] =
    useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [lastResponse, setLastResponse] =
    useState<ChatResponse | null>(null);

  const chatContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const storedSession =
      window.localStorage.getItem("travelx-session-id");
    const activeSession = storedSession || createId();

    window.localStorage.setItem(
      "travelx-session-id",
      activeSession,
    );
    setSessionId(activeSession);
  }, []);

  useEffect(() => {
   const container = chatContainerRef.current;

  if (!container) {
    return;
  }

  const animationFrame = requestAnimationFrame(() => {
    container.scrollTo({
      top: container.scrollHeight,
      behavior: "smooth",
    });
  });

  return () => cancelAnimationFrame(animationFrame);
}, [messages, isSending]);

  async function sendMessage(
    rawMessage: string,
    draftVersion?: number,
  ) {
    const message = rawMessage.trim();

    if (!message || isSending) {
      return;
    }

    const activeSession = sessionId || createId();

    if (!sessionId) {
      setSessionId(activeSession);
      window.localStorage.setItem(
        "travelx-session-id",
        activeSession,
      );
    }

    setMessages((current) => [
      ...current,
      {
        id: createId(),
        role: "user",
        text: message,
      },
    ]);
    setInput("");
    setIsSending(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message,
          session_id: activeSession,
          ...(draftVersion
            ? { draft_version: draftVersion }
            : {}),
        }),
      });

      const payload = (await response.json()) as
        | ChatResponse
        | { detail?: string };

      if (!response.ok) {
        const detail =
          "detail" in payload && payload.detail
            ? payload.detail
            : "تعذر معالجة الطلب.";

        throw new Error(detail);
      }

      const chatResponse = payload as ChatResponse;

      setLastResponse(chatResponse);
      setMessages((current) => [
        ...current,
        {
          id: createId(),
          role: "assistant",
          text: chatResponse.reply,
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: createId(),
          role: "error",
          text:
            error instanceof Error
              ? error.message
              : "تعذر الاتصال بالخدمة مؤقتًا.",
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(input);
  }

  function handleKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      void sendMessage(input);
    }
  }

  function startNewConversation() {
    const newSession = createId();

    window.localStorage.setItem(
      "travelx-session-id",
      newSession,
    );
    setSessionId(newSession);
    setMessages(initialMessages);
    setLastResponse(null);
    setInput("");
  }

  

  const draft = lastResponse?.ticket_draft;
  const ticket = lastResponse?.ticket;

  return (
    <main className="agent-shell fixed inset-0 overflow-hidden text-white">
      <div className="agent-grid pointer-events-none absolute inset-0 opacity-70" />

      <div className="agent-orb pointer-events-none absolute -right-40 -top-48 h-[32rem] w-[32rem] bg-cyan-500/10" />
      <div className="agent-orb agent-orb-secondary pointer-events-none absolute -bottom-52 -left-44 h-[34rem] w-[34rem] bg-violet-600/10" />

      <div
        dir="ltr"
        className="relative mx-auto flex h-full max-w-[1750px] overflow-hidden border-x border-white/[0.07] bg-[#040914]/55 shadow-2xl shadow-black/40 backdrop-blur-sm"
      >
        <section
          dir="rtl"
          className="flex min-w-0 flex-1 flex-col"
        >
          <header className="panel-enter flex h-[76px] shrink-0 items-center justify-between border-b border-white/[0.08] bg-[#07101d]/80 px-5 backdrop-blur-xl lg:px-8">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-300 to-blue-600 text-sm font-black text-[#03111c] lg:hidden">
                TX
              </div>

              <div>
                <h1 className="font-bold text-slate-100">
                  مساعد Travel-X
                </h1>

                <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
                  <span className="status-dot h-2 w-2 rounded-full bg-emerald-400" />
                  <span>
                    {isSending
                      ? "جاري تحليل طلبك..."
                      : lastResponse
                        ? stageLabels[
                            lastResponse.stage
                          ] ?? lastResponse.stage
                        : "جاهز لمساعدتك"}
                  </span>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={startNewConversation}
              className="group flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.045] px-4 py-2.5 text-xs font-medium text-slate-300 transition hover:border-cyan-400/30 hover:bg-cyan-400/[0.08] hover:text-white"
            >
              <span className="text-lg leading-none text-cyan-300 transition group-hover:rotate-90">
                +
              </span>
              <span>محادثة جديدة</span>
            </button>
          </header>

          <div className="flex gap-2 overflow-x-auto border-b border-white/[0.07] bg-[#050b17]/75 px-4 py-3 lg:hidden">
            {quickServices.map((service) => (
              <button
                key={service.department}
                type="button"
                disabled={isSending}
                onClick={() =>
                  void sendMessage(service.prompt)
                }
                className="shrink-0 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-xs text-slate-300 transition hover:border-cyan-400/30 hover:text-cyan-200"
              >
                {service.title}
              </button>
            ))}
          </div>

          <div
  ref={chatContainerRef}
  className="chat-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain"
>
            <div className="mx-auto w-full max-w-[980px] space-y-6 px-4 py-8 sm:px-6 lg:px-10 lg:py-10">
              {messages.map((message) => {
                const isUser =
                  message.role === "user";
                const isError =
                  message.role === "error";

                return (
                  <div
                    key={message.id}
                    dir="ltr"
                    className={`flex ${
                      isUser
                        ? "message-user-enter justify-end"
                        : "message-assistant-enter justify-start"
                    }`}
                  >
                    <div
                      className={`flex max-w-[88%] items-end gap-3 lg:max-w-[78%] ${
                        isUser
                          ? "flex-row-reverse"
                          : ""
                      }`}
                    >
                      <div
                        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[11px] font-black ${
                          isUser
                            ? "bg-white/[0.07] text-slate-300"
                            : isError
                              ? "border border-red-400/20 bg-red-400/10 text-red-300"
                              : "bg-gradient-to-br from-cyan-300 to-blue-600 text-[#03111c] shadow-lg shadow-cyan-500/10"
                        }`}
                      >
                        {isUser
                          ? "أنت"
                          : isError
                            ? "!"
                            : "TX"}
                      </div>

                      <div
                        dir="rtl"
                        className={`rounded-2xl px-5 py-3.5 text-sm leading-7 shadow-lg ${
                          isUser
                            ? "rounded-br-md bg-gradient-to-br from-cyan-400 to-blue-500 font-medium text-[#03111c] shadow-cyan-500/10"
                            : isError
                              ? "rounded-bl-md border border-red-400/20 bg-red-400/[0.09] text-red-100 shadow-black/10"
                              : "rounded-bl-md border border-white/[0.09] bg-[#111827]/90 text-slate-200 shadow-black/15"
                        }`}
                      >
                        <p className="whitespace-pre-wrap">
                          {message.text}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}

              {isSending && (
                <div
                  dir="ltr"
                  className="message-assistant-enter flex justify-start"
                >
                  <div className="flex items-end gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-300 to-blue-600 text-[11px] font-black text-[#03111c]">
                      TX
                    </div>

                    <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-white/[0.09] bg-[#111827]/90 px-5 py-4">
                      <span className="typing-dot h-2 w-2 rounded-full bg-cyan-300" />
                      <span className="typing-dot h-2 w-2 rounded-full bg-cyan-300" />
                      <span className="typing-dot h-2 w-2 rounded-full bg-cyan-300" />
                    </div>
                  </div>
                </div>
              )}

              
            </div>
          </div>

          {lastResponse && (
            <div className="flex shrink-0 flex-wrap justify-center gap-2 border-t border-white/[0.06] bg-[#050b16]/70 px-4 py-2.5">
              {lastResponse.primary_department && (
                <span className="rounded-full border border-cyan-400/15 bg-cyan-400/[0.07] px-3 py-1 text-[10px] font-semibold text-cyan-300">
                  {lastResponse.primary_department.toUpperCase()}
                </span>
              )}

              {lastResponse.service_key && (
                <span className="rounded-full border border-violet-400/15 bg-violet-400/[0.07] px-3 py-1 text-[10px] text-violet-300">
                  {serviceLabels[
                    lastResponse.service_key
                  ] ?? lastResponse.service_key}
                </span>
              )}

              {lastResponse.missing_requirements
                .length > 0 && (
                <span className="rounded-full border border-amber-400/15 bg-amber-400/[0.07] px-3 py-1 text-[10px] text-amber-300">
                  متطلبات متبقية:{" "}
                  {
                    lastResponse
                      .missing_requirements.length
                  }
                </span>
              )}
            </div>
          )}

          <footer className="shrink-0 border-t border-white/[0.08] bg-[#050a14]/95 px-4 py-4 backdrop-blur-xl sm:px-6 lg:px-8">
            <form
              onSubmit={handleSubmit}
              className="mx-auto max-w-[980px]"
            >
              <div className="flex items-end gap-3 rounded-2xl border border-white/[0.1] bg-[#0b1322]/95 p-2 shadow-2xl shadow-black/25 transition duration-300 focus-within:border-cyan-400/40 focus-within:shadow-cyan-500/5">
                <textarea
                  value={input}
                  disabled={isSending}
                  rows={1}
                  placeholder="اكتب سؤالك أو صف الخدمة التي تحتاجها..."
                  onChange={(event) =>
                    setInput(event.target.value)
                  }
                  onKeyDown={handleKeyDown}
                  className="max-h-32 min-h-12 flex-1 resize-none bg-transparent px-3 py-3 text-sm leading-6 text-white outline-none placeholder:text-slate-500 disabled:opacity-50"
                />

                <button
                  type="submit"
                  aria-label="إرسال الرسالة"
                  disabled={
                    !input.trim() || isSending
                  }
                  className="group flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-300 to-blue-500 text-[#03111c] shadow-lg shadow-cyan-500/15 transition duration-300 hover:-translate-y-0.5 hover:shadow-cyan-400/25 disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:translate-y-0"
                >
                  <svg
                    viewBox="0 0 24 24"
                    className="h-5 w-5 -rotate-45 transition-transform group-hover:translate-x-0.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path
                      d="M22 2 11 13"
                      strokeLinecap="round"
                    />
                    <path
                      d="m22 2-7 20-4-9-9-4Z"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
              </div>

              <p className="mt-2 text-center text-[10px] text-slate-600">
                Enter للإرسال · Shift + Enter لسطر جديد
              </p>
            </form>
          </footer>
        </section>

        <aside
  dir="rtl"
  className="chat-scrollbar hidden h-full w-[350px] shrink-0 flex-col overflow-y-auto border-l border-white/[0.08] bg-[#070c18]/92 p-5 backdrop-blur-xl lg:flex"
>
          <div className="panel-enter flex items-center gap-3 border-b border-white/[0.08] pb-5">
            <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-300 via-sky-400 to-blue-600 font-black text-[#03111c] shadow-xl shadow-cyan-500/15">
              TX
              <span className="absolute -bottom-1 -left-1 h-3.5 w-3.5 rounded-full border-2 border-[#070c18] bg-emerald-400" />
            </div>

            <div>
              <h2 className="text-lg font-black tracking-wide">
                Travel-X AI
              </h2>
              <p className="mt-0.5 text-[11px] text-slate-500">
                بوابة خدمات العملاء
              </p>
            </div>
          </div>

          <div className="mt-6">
            <p className="text-[10px] font-semibold tracking-wider text-cyan-300">
              اختر نقطة البداية
            </p>
            <h3 className="mt-1 text-base font-bold">
              خدمات الشركة
            </h3>
          </div>

          <div className="mt-4 space-y-3">
            {quickServices.map(
              (service, index) => (
                <button
                  key={service.department}
                  type="button"
                  disabled={isSending}
                  onClick={() =>
                    void sendMessage(service.prompt)
                  }
                  style={{
                    animationDelay: `${index * 80}ms`,
                  }}
                  className="service-card panel-enter w-full rounded-2xl border border-white/[0.09] bg-[#0b1322]/75 p-4 text-right disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <div className="relative z-10 flex items-center justify-between gap-3">
                    <h4 className="text-sm font-bold text-slate-100">
                      {service.title}
                    </h4>

                    <span className="rounded-lg border border-cyan-400/15 bg-cyan-400/[0.07] px-2 py-1 text-[9px] font-semibold text-cyan-300">
                      {service.department}
                    </span>
                  </div>

                  <p className="relative z-10 mt-2 text-[11px] leading-5 text-slate-500">
                    {service.description}
                  </p>
                </button>
              ),
            )}
          </div>

          <div className="mt-auto pt-5">
            {ticket ? (
              <div className="panel-enter rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.07] p-4">
                <p className="text-[10px] font-semibold text-emerald-300">
                  تم إنشاء التذكرة بنجاح
                </p>
                <p className="mt-2 font-mono text-sm font-bold text-white">
                  {ticket.ticket_number}
                </p>
                <p className="mt-1 text-[11px] text-slate-400">
                  الحالة: {ticket.status}
                </p>
              </div>
            ) : draft ? (
              <div className="panel-enter rounded-2xl border border-cyan-400/20 bg-cyan-400/[0.055] p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-bold">
                    مسودة التذكرة
                  </p>
                  <span className="rounded-md bg-cyan-400/10 px-2 py-1 text-[9px] text-cyan-300">
                    الإصدار {draft.version}
                  </span>
                </div>

                <p className="mt-2 text-[11px] text-slate-400">
                  {serviceLabels[draft.service_key] ??
                    draft.service_key}
                </p>

                <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                  <div className="h-full w-full rounded-full bg-gradient-to-l from-cyan-300 to-blue-500" />
                </div>

                <p className="mt-2 text-[10px] text-slate-500">
                  تم جمع{" "}
                  {Object.keys(
                    draft.requirements,
                  ).length}{" "}
                  متطلبات
                </p>

                <button
                  type="button"
                  disabled={isSending}
                  onClick={() =>
                    void sendMessage(
                      "موافق، أنشئ التذكرة",
                      draft.version,
                    )
                  }
                  className="mt-4 w-full rounded-xl bg-gradient-to-l from-cyan-300 to-blue-500 px-4 py-3 text-xs font-black text-[#03111c] transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-cyan-500/15 disabled:opacity-40"
                >
                  تأكيد وإنشاء التذكرة
                </button>
              </div>
            ) : (
              <div className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-4">
                <p className="text-[11px] leading-5 text-slate-500">
                  لن يتم إنشاء تذكرة قبل جمع
                  المتطلبات وعرض المسودة عليك
                  للمراجعة.
                </p>
              </div>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
import { NextResponse } from "next/server";

const backendUrl =
  process.env.TRAVELX_API_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request) {
  let body: unknown;

  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { detail: "محتوى الطلب غير صالح." },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(`${backendUrl}/v1/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });

    const responseText = await response.text();

    let payload: unknown;

    try {
      payload = JSON.parse(responseText);
    } catch {
      payload = {
        detail: responseText || "استجابة غير صالحة من الخدمة الخلفية.",
      };
    }

    return NextResponse.json(payload, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      {
        detail:
          "تعذر الاتصال بخدمة Travel-X مؤقتًا. حاول مرة أخرى.",
      },
      { status: 503 },
    );
  }
}
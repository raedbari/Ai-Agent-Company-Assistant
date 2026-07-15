import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  SESSION_COOKIE_NAME,
  verifySessionToken,
} from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Department = "txsaas" | "cybtx" | "destination";

type RouteContext = {
  params: Promise<{
    department: string;
  }>;
};

const ALLOWED_DEPARTMENTS = new Set<Department>([
  "txsaas",
  "cybtx",
  "destination",
]);

export async function GET(
  request: Request,
  context: RouteContext,
) {
  const cookieStore = await cookies();

  const token = cookieStore.get(
    SESSION_COOKIE_NAME,
  )?.value;

  const session = await verifySessionToken(token);

  if (!session) {
    return NextResponse.json(
      { detail: "غير مصرح بعرض التذاكر" },
      {
        status: 401,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  const { department } = await context.params;

  if (
    !ALLOWED_DEPARTMENTS.has(
      department as Department,
    )
  ) {
    return NextResponse.json(
      { detail: "القسم المطلوب غير موجود" },
      { status: 404 },
    );
  }

  const backendUrl = process.env.TRAVELX_API_URL?.replace(
    /\/+$/,
    "",
  );

  if (!backendUrl) {
    return NextResponse.json(
      { detail: "عنوان خدمة Travel-X غير مضبوط" },
      { status: 503 },
    );
  }

  const requestUrl = new URL(request.url);
  const requestedLimit = Number(
    requestUrl.searchParams.get("limit") ?? "50",
  );

  const limit =
    Number.isInteger(requestedLimit) &&
    requestedLimit >= 1 &&
    requestedLimit <= 100
      ? requestedLimit
      : 50;

  try {
    const backendResponse = await fetch(
      `${backendUrl}/v1/departments/${department}/tickets?limit=${limit}`,
      {
        method: "GET",
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      },
    );

    const responseBody = await backendResponse.text();

    return new Response(responseBody, {
      status: backendResponse.status,
      headers: {
        "Content-Type":
          backendResponse.headers.get("content-type") ??
          "application/json; charset=utf-8",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "تعذر الاتصال بخدمة التذاكر" },
      { status: 502 },
    );
  }
}
import { NextRequest, NextResponse } from "next/server";

import {
  SESSION_COOKIE_NAME,
  verifySessionToken,
} from "@/lib/auth";

export default async function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  const token = request.cookies.get(
    SESSION_COOKIE_NAME,
  )?.value;

  const session = await verifySessionToken(token);

  if (pathname === "/login") {
    if (session) {
      return NextResponse.redirect(
        new URL("/tickets", request.url),
      );
    }

    return NextResponse.next();
  }

  if (!session) {
    if (pathname.startsWith("/api/departments/")) {
      return NextResponse.json(
        { detail: "يجب تسجيل الدخول لعرض التذاكر" },
        {
          status: 401,
          headers: {
            "Cache-Control": "no-store",
          },
        },
      );
    }

    return NextResponse.redirect(
      new URL("/login", request.url),
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/login",
    "/tickets/:path*",
    "/api/departments/:path*",
  ],
};
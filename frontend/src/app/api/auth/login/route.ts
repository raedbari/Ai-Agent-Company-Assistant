import { compare } from "bcryptjs";
import { NextResponse } from "next/server";

import {
  createSessionToken,
  SESSION_COOKIE_NAME,
  SESSION_MAX_AGE_SECONDS,
} from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type LoginBody = {
  username?: unknown;
  password?: unknown;
};

function configurationError() {
  return NextResponse.json(
    { detail: "إعدادات تسجيل الدخول غير مكتملة" },
    { status: 503 },
  );
}

export async function POST(request: Request) {
  let body: LoginBody;

  try {
    body = (await request.json()) as LoginBody;
  } catch {
    return NextResponse.json(
      { detail: "بيانات الطلب غير صحيحة" },
      { status: 400 },
    );
  }

  const username =
    typeof body.username === "string" ? body.username.trim() : "";

  const password =
    typeof body.password === "string" ? body.password : "";

  if (
    !username ||
    !password ||
    username.length > 128 ||
    password.length > 256
  ) {
    return NextResponse.json(
      { detail: "اسم المستخدم أو كلمة المرور غير صحيحة" },
      { status: 401 },
    );
  }

  const expectedUsername =
    process.env.TRAVELX_ADMIN_USERNAME;

  const encodedPasswordHash =
    process.env.TRAVELX_ADMIN_PASSWORD_HASH_B64;

  if (!expectedUsername || !encodedPasswordHash) {
    return configurationError();
  }

  const passwordHash = Buffer.from(
    encodedPasswordHash,
    "base64",
  ).toString("utf8");

  if (!passwordHash.startsWith("$2")) {
    return configurationError();
  }

  const passwordMatches = await compare(password, passwordHash);
  const usernameMatches = username === expectedUsername;

  if (!usernameMatches || !passwordMatches) {
    await new Promise((resolve) => setTimeout(resolve, 400));

    return NextResponse.json(
      { detail: "اسم المستخدم أو كلمة المرور غير صحيحة" },
      {
        status: 401,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  let token: string;

  try {
    token = await createSessionToken(username);
  } catch {
    return configurationError();
  }

  const response = NextResponse.json({ authenticated: true });

  response.headers.set("Cache-Control", "no-store");

  response.cookies.set({
    name: SESSION_COOKIE_NAME,
    value: token,
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  });

  return response;
}
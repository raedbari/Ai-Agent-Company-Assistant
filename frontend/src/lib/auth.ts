import { jwtVerify, SignJWT } from "jose";

export const SESSION_COOKIE_NAME = "travelx_admin_session";
export const SESSION_MAX_AGE_SECONDS = 8 * 60 * 60;

const SESSION_ISSUER = "travelx-frontend";
const SESSION_AUDIENCE = "travelx-ticket-admin";

export type AdminSession = {
  username: string;
  role: "admin";
};

function sessionSecret(): Uint8Array {
  const secret = process.env.TRAVELX_AUTH_SECRET;

  if (!secret || secret.length < 32) {
    throw new Error(
      "TRAVELX_AUTH_SECRET is missing or shorter than 32 characters",
    );
  }

  return new TextEncoder().encode(secret);
}

export async function createSessionToken(
  username: string,
): Promise<string> {
  return new SignJWT({
    username,
    role: "admin",
  })
    .setProtectedHeader({
      alg: "HS256",
      typ: "JWT",
    })
    .setIssuer(SESSION_ISSUER)
    .setAudience(SESSION_AUDIENCE)
    .setSubject(username)
    .setIssuedAt()
    .setExpirationTime(`${SESSION_MAX_AGE_SECONDS}s`)
    .sign(sessionSecret());
}

export async function verifySessionToken(
  token: string | undefined,
): Promise<AdminSession | null> {
  if (!token) {
    return null;
  }

  try {
    const { payload } = await jwtVerify(
      token,
      sessionSecret(),
      {
        algorithms: ["HS256"],
        issuer: SESSION_ISSUER,
        audience: SESSION_AUDIENCE,
      },
    );

    if (
      payload.role !== "admin" ||
      typeof payload.username !== "string"
    ) {
      return null;
    }

    return {
      username: payload.username,
      role: "admin",
    };
  } catch {
    return null;
  }
}
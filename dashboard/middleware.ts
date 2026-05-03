import { NextRequest, NextResponse } from "next/server";

const REALM = 'Basic realm="Arbitrage Dashboard", charset="UTF-8"';

export function middleware(req: NextRequest) {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) {
    if (process.env.NODE_ENV === "production") {
      console.warn(
        "[middleware] DASHBOARD_PASSWORD not set — dashboard is publicly accessible"
      );
    }
    return NextResponse.next();
  }

  const user = process.env.DASHBOARD_USER || "admin";
  const auth = req.headers.get("authorization");

  if (auth?.startsWith("Basic ")) {
    const decoded = atob(auth.slice(6));
    const sep = decoded.indexOf(":");
    if (sep !== -1) {
      const u = decoded.slice(0, sep);
      const p = decoded.slice(sep + 1);
      if (u === user && p === password) {
        return NextResponse.next();
      }
    }
  }

  return new NextResponse("Authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": REALM },
  });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

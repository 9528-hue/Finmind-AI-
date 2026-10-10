import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export async function POST(request: Request) {
  try {
    const authorization = request.headers.get("authorization");
    const backendRes = await fetch(`${BACKEND_URL}/ai/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authorization ? { Authorization: authorization } : {}),
      },
      body: JSON.stringify(await request.json()),
    });

    const body = await backendRes.json();
    return NextResponse.json(body, { status: backendRes.status });
  } catch (error) {
    console.error("FINMIND AI backend request failed:", error);
    return NextResponse.json(
      { detail: "AI assistant backend is unavailable. Please try again." },
      { status: 502 }
    );
  }
}

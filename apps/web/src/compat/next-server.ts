export class NextResponse extends Response {
  static json(data: unknown, init?: ResponseInit) {
    const body = JSON.stringify(data);
    return new NextResponse(body, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {})
      }
    });
  }
}

export type NextRequest = Request;

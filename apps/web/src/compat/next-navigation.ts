export function usePathname(): string {
  if (typeof window === "undefined") return "";
  return window.location.pathname;
}

export function useSearchParams(): URLSearchParams {
  if (typeof window === "undefined") return new URLSearchParams();
  return new URLSearchParams(window.location.search);
}

export function useParams<T extends Record<string, string> = Record<string, string>>(): T {
  if (typeof window === "undefined") return {} as T;
  const params = (window as unknown as { __astroParams?: T }).__astroParams;
  return (params || {}) as T;
}

export function useRouter() {
  return {
    push(href: string) {
      if (typeof window !== "undefined") window.location.assign(href);
    },
    replace(href: string) {
      if (typeof window !== "undefined") window.location.replace(href);
    },
    back() {
      if (typeof window !== "undefined") window.history.back();
    }
  };
}

export function redirect(href: string): never {
  if (typeof window !== "undefined") {
    window.location.assign(href);
  }
  throw new Error(`Redirect to ${href}`);
}

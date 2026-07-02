"use client";

import { AuthMode } from "@/auth/mode";

let localToken: string | null = null;
const STORAGE_KEY = "mc_local_auth_token";

export const LOCAL_AUTH_TOKEN_MIN_LENGTH = 50;

export function isLocalAuthMode(): boolean {
  return process.env.NEXT_PUBLIC_AUTH_MODE === AuthMode.Local;
}

export function getConfiguredLocalAuthToken(): string | null {
  const configured = process.env.NEXT_PUBLIC_LOCAL_AUTH_TOKEN?.trim();
  return configured || null;
}

export function setLocalAuthToken(token: string): void {
  localToken = token;
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, token);
  } catch {
    // Ignore storage failures (private mode / policy).
  }
}

export function getLocalAuthToken(): string | null {
  if (localToken) return localToken;
  if (typeof window === "undefined") {
    return getConfiguredLocalAuthToken();
  }
  try {
    const stored = window.sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      localToken = stored;
      return stored;
    }
  } catch {
    // Ignore storage failures (private mode / policy).
  }
  return getConfiguredLocalAuthToken();
}

export function clearLocalAuthToken(): void {
  localToken = null;
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore storage failures (private mode / policy).
  }
}

export function getTokenFromUrl(): string | null {
  if (typeof window === "undefined") return null;
  const token = new URLSearchParams(window.location.search).get("token")?.trim();
  return token || null;
}

export function removeTokenFromUrl(): void {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams(window.location.search);
  if (!params.has("token")) return;
  params.delete("token");
  const newSearch = params.toString();
  const newUrl = `${window.location.pathname}${newSearch ? `?${newSearch}` : ""}${window.location.hash}`;
  window.history.replaceState({}, "", newUrl);
}

export async function validateLocalToken(token: string): Promise<string | null> {
  const rawBaseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!rawBaseUrl) {
    return "NEXT_PUBLIC_API_URL is not set.";
  }

  const baseUrl = rawBaseUrl.replace(/\/+$/, "");

  let response: Response;
  try {
    response = await fetch(`${baseUrl}/api/v1/users/me`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    return "Unable to reach backend to validate token.";
  }

  if (response.ok) {
    return null;
  }
  if (response.status === 401 || response.status === 403) {
    return "Token is invalid.";
  }
  return `Unable to validate token (HTTP ${response.status}).`;
}

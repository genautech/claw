import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearLocalAuthToken,
  getConfiguredLocalAuthToken,
  getLocalAuthToken,
  getTokenFromUrl,
  removeTokenFromUrl,
  setLocalAuthToken,
  validateLocalToken,
} from "@/auth/localAuth";

const fetchMock = vi.fn();

describe("localAuth", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    clearLocalAuthToken();
    window.sessionStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    clearLocalAuthToken();
    window.sessionStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  describe("getConfiguredLocalAuthToken", () => {
    it("returns trimmed env token when configured", () => {
      vi.stubEnv(
        "NEXT_PUBLIC_LOCAL_AUTH_TOKEN",
        `  ${"a".repeat(50)}  `,
      );

      expect(getConfiguredLocalAuthToken()).toBe("a".repeat(50));
    });

    it("returns null when env token is empty", () => {
      vi.stubEnv("NEXT_PUBLIC_LOCAL_AUTH_TOKEN", "   ");

      expect(getConfiguredLocalAuthToken()).toBeNull();
    });
  });

  describe("getLocalAuthToken", () => {
    it("prefers session storage over configured env token", () => {
      vi.stubEnv("NEXT_PUBLIC_LOCAL_AUTH_TOKEN", "e".repeat(50));
      setLocalAuthToken("s".repeat(50));

      expect(getLocalAuthToken()).toBe("s".repeat(50));
    });

    it("falls back to configured env token when storage is empty", () => {
      vi.stubEnv("NEXT_PUBLIC_LOCAL_AUTH_TOKEN", "e".repeat(50));

      expect(getLocalAuthToken()).toBe("e".repeat(50));
    });
  });

  describe("getTokenFromUrl", () => {
    it("reads token from query string", () => {
      window.history.replaceState({}, "", `/?token=${"t".repeat(50)}`);

      expect(getTokenFromUrl()).toBe("t".repeat(50));
    });

    it("returns null when token query param is missing", () => {
      window.history.replaceState({}, "", "/boards");

      expect(getTokenFromUrl()).toBeNull();
    });
  });

  describe("removeTokenFromUrl", () => {
    it("removes token from the URL while preserving other params", () => {
      window.history.replaceState(
        {},
        "",
        `/?token=${"t".repeat(50)}&tab=ops#section`,
      );

      removeTokenFromUrl();

      expect(window.location.pathname).toBe("/");
      expect(window.location.search).toBe("?tab=ops");
      expect(window.location.hash).toBe("#section");
    });
  });

  describe("validateLocalToken", () => {
    beforeEach(() => {
      vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000/");
    });

    it("returns null when backend accepts the token", async () => {
      fetchMock.mockResolvedValueOnce(new Response(null, { status: 200 }));

      await expect(validateLocalToken("g".repeat(50))).resolves.toBeNull();
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/users/me",
        expect.objectContaining({
          method: "GET",
          headers: { Authorization: `Bearer ${"g".repeat(50)}` },
        }),
      );
    });

    it("returns an invalid-token message for 401 responses", async () => {
      fetchMock.mockResolvedValueOnce(new Response(null, { status: 401 }));

      await expect(validateLocalToken("g".repeat(50))).resolves.toBe(
        "Token is invalid.",
      );
    });

    it("returns a network error when backend is unreachable", async () => {
      fetchMock.mockRejectedValueOnce(new TypeError("network error"));

      await expect(validateLocalToken("g".repeat(50))).resolves.toBe(
        "Unable to reach backend to validate token.",
      );
    });

    it("returns an error when NEXT_PUBLIC_API_URL is missing", async () => {
      vi.stubEnv("NEXT_PUBLIC_API_URL", "");

      await expect(validateLocalToken("g".repeat(50))).resolves.toBe(
        "NEXT_PUBLIC_API_URL is not set.",
      );
      expect(fetchMock).not.toHaveBeenCalled();
    });
  });
});

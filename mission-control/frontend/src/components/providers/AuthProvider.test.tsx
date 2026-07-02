import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { AuthProvider } from "@/components/providers/AuthProvider";
import { clearLocalAuthToken } from "@/auth/localAuth";

const fetchMock = vi.fn();

describe("AuthProvider local auth", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    clearLocalAuthToken();
    window.sessionStorage.clear();
    window.history.replaceState({}, "", "/");
    vi.stubEnv("NEXT_PUBLIC_AUTH_MODE", "local");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000/");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    clearLocalAuthToken();
    window.sessionStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("skips the login screen when NEXT_PUBLIC_LOCAL_AUTH_TOKEN is configured", () => {
    vi.stubEnv("NEXT_PUBLIC_LOCAL_AUTH_TOKEN", "e".repeat(50));

    render(
      <AuthProvider>
        <div data-testid="app-content">Mission Control</div>
      </AuthProvider>,
    );

    expect(screen.getByTestId("app-content")).toBeInTheDocument();
    expect(
      screen.queryByText("Local Authentication"),
    ).not.toBeInTheDocument();
  });

  it("auto-logs in from a valid token in the URL", async () => {
    const token = "g".repeat(50);
    window.history.replaceState({}, "", `/?token=${encodeURIComponent(token)}`);
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 200 }));

    render(
      <AuthProvider>
        <div data-testid="app-content">Mission Control</div>
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("app-content")).toBeInTheDocument(),
    );
    expect(window.location.search).not.toContain("token=");
    expect(window.sessionStorage.getItem("mc_local_auth_token")).toBe(token);
  });

  it("shows the login screen when URL token validation fails", async () => {
    const token = "x".repeat(50);
    window.history.replaceState({}, "", `/?token=${encodeURIComponent(token)}`);
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 401 }));

    render(
      <AuthProvider>
        <div data-testid="app-content">Mission Control</div>
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByText("Local Authentication")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("app-content")).not.toBeInTheDocument();
    expect(screen.getByText("Token is invalid.")).toBeInTheDocument();
    expect(window.location.search).not.toContain("token=");
  });
});

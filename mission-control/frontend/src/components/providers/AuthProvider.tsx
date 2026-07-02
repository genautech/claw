"use client";

import { ClerkProvider } from "@clerk/nextjs";
import { useEffect, useState, type ReactNode } from "react";

import { isLikelyValidClerkPublishableKey } from "@/auth/clerkKey";
import {
  clearLocalAuthToken,
  getLocalAuthToken,
  getTokenFromUrl,
  isLocalAuthMode,
  removeTokenFromUrl,
  setLocalAuthToken,
  validateLocalToken,
} from "@/auth/localAuth";
import { LocalAuthLogin } from "@/components/organisms/LocalAuthLogin";

function LocalAuthLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-app">
      <p className="text-sm text-muted">Validating access token...</p>
    </div>
  );
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const localMode = isLocalAuthMode();
  const [localAuthReady, setLocalAuthReady] = useState(() => {
    if (!localMode || typeof window === "undefined") return true;
    return !getTokenFromUrl();
  });
  const [urlAuthError, setUrlAuthError] = useState<string | null>(null);

  useEffect(() => {
    if (!localMode) {
      clearLocalAuthToken();
    }
  }, [localMode]);

  useEffect(() => {
    if (!localMode) return;

    const urlToken = getTokenFromUrl();
    if (!urlToken) {
      setLocalAuthReady(true);
      return;
    }

    let cancelled = false;
    void validateLocalToken(urlToken).then((validationError) => {
      if (cancelled) return;

      removeTokenFromUrl();
      if (validationError) {
        setUrlAuthError(validationError);
      } else {
        setLocalAuthToken(urlToken);
        setUrlAuthError(null);
      }
      setLocalAuthReady(true);
    });

    return () => {
      cancelled = true;
    };
  }, [localMode]);

  if (localMode) {
    if (!localAuthReady) {
      return <LocalAuthLoading />;
    }
    if (!getLocalAuthToken()) {
      return <LocalAuthLogin initialError={urlAuthError} />;
    }
    return <>{children}</>;
  }

  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  const afterSignOutUrl =
    process.env.NEXT_PUBLIC_CLERK_AFTER_SIGN_OUT_URL ?? "/";

  if (!isLikelyValidClerkPublishableKey(publishableKey)) {
    return <>{children}</>;
  }

  return (
    <ClerkProvider
      publishableKey={publishableKey}
      afterSignOutUrl={afterSignOutUrl}
    >
      {children}
    </ClerkProvider>
  );
}

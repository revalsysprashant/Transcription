// Sign-in flow: Google returns a credential → POST /auth/google sets HttpOnly cookies → notify App to fetch and display the user.
import { useEffect, useRef, useState } from "react";
import { API_URL } from "../auth";

interface GoogleCredentialResponse {
  credential: string;
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: GoogleCredentialResponse) => void;
          }) => void;

          renderButton: (
            element: HTMLElement,
            options: {
              theme?: "outline" | "filled_blue" | "filled_black";
              size?: "large" | "medium" | "small";
              shape?: "rectangular" | "pill" | "circle" | "square";
              text?: "signin_with" | "signup_with" | "continue_with" | "signin";
              width?: number;
            }
          ) => void;
        };
      };
    };
  }
}

export default function GoogleLoginButton({ onLogin }: { onLogin: () => Promise<void> }) {
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const onLoginRef = useRef(onLogin);

  useEffect(() => { onLoginRef.current = onLogin; }, [onLogin]);
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
  async function handleCredentialResponse(
    response: GoogleCredentialResponse
  ) {
    setError("");
    setPending(true);
    try {
      const apiResponse = await fetch(
        `${API_URL}/auth/google`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify({
            credential: response.credential,
          }),
        }
      );

      if (!apiResponse.ok) {
        throw new Error("Google login failed. Please try again.");
      }

      await onLoginRef.current();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to sign in. Please try again.");
    } finally {
      setPending(false);
    }
  }

    if (!window.google || !buttonRef.current) {
      return;
    }

    window.google.accounts.id.initialize({
      client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
      callback: handleCredentialResponse,
    });

    window.google.accounts.id.renderButton(buttonRef.current, {
      theme: "outline",
      size: "large",
      shape: "rectangular",
      text: "continue_with",
      width: 360,
    });
  }, []);


  return (
    <div className="w-full" aria-busy={pending}>
      {pending && <p role="status" className="mb-3 text-sm text-zinc-500">Signing in…</p>}
      {error && <p role="alert" className="mb-3 text-sm text-red-600">{error}</p>}
      <div
        ref={buttonRef}
        className="flex w-full justify-center overflow-hidden rounded-xl"
      />
    </div>
  );
}

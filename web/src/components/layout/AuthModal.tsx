import { LockKeyhole, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { getAuthCallbackUrl, getSupabaseClient, isSupabaseConfigured } from "@/lib/supabase";

interface AuthModalProps {
  open: boolean;
  externalError?: string;
  onClose: () => void;
  onSignedIn: () => void;
}

export default function AuthModal({
  open,
  externalError = "",
  onClose,
  onSignedIn,
}: AuthModalProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  if (!open) return null;

  const configured = isSupabaseConfigured();
  const displayError = error || externalError;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");

    if (!configured) {
      setError(
        "Supabase publishable env vars (NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY) are not configured.",
      );
      return;
    }

    if (!email.trim() || !password) {
      setError("Enter your Owner email and password.");
      return;
    }

    setSubmitting(true);
    try {
      const supabase = getSupabaseClient();
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (signInError) {
        setError(signInError.message);
        return;
      }
      setPassword("");
      onSignedIn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleResetPassword = async () => {
    setError("");
    setNotice("");
    if (!configured || !email.trim()) {
      setError("Enter your Owner email address first.");
      return;
    }
    setSubmitting(true);
    try {
      const supabase = getSupabaseClient();
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(email.trim(), {
        redirectTo: getAuthCallbackUrl(),
      });
      if (resetError) {
        setError(resetError.message);
      } else {
        setNotice("Password reset link sent. Check your inbox.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send password reset email.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="auth-modal" onMouseDown={(e) => e.stopPropagation()}>
        <button className="modal-close" type="button" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>
        <div className="auth-icon">
          <LockKeyhole size={22} />
        </div>
        <span className="eyebrow">Private Owner Access</span>
        <h2>Unlock ProspectIQ live data.</h2>
        <p>
          Public visitors explore static demo data only. Sign in with an authorized owner account
          to access live leads, CRM notes, and scraper automation.
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          {displayError && <div className="auth-error">{displayError}</div>}
          {notice && <div className="auth-notice">{notice}</div>}
          <label>
            Owner Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              autoComplete="email"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password"
              required
            />
          </label>
          <button className="dispatch-button" type="submit" disabled={submitting}>
            {submitting ? "Verifying Owner session..." : "Sign in as Owner"}
          </button>
        </form>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <button className="text-button" type="button" onClick={handleResetPassword} disabled={submitting}>
            Forgot password?
          </button>
          <button className="text-button" type="button" onClick={onClose}>
            Continue demo preview
          </button>
        </div>
      </div>
    </div>
  );
}

"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import type { EmailOtpType } from "@supabase/supabase-js";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export default function AuthCallback() {
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [complete, setComplete] = useState(false);

  useEffect(() => {
    let mounted = true;
    const supabase = getSupabaseBrowserClient();
    const inspectSession = async () => {
      const hash = new URLSearchParams(window.location.hash.slice(1));
      const query = new URLSearchParams(window.location.search);
      const authError = hash.get("error_description") ?? query.get("error_description");
      if (authError) {
        if (mounted) setError(decodeURIComponent(authError.replaceAll("+", " ")));
        return;
      }

      // Supabase may have already consumed the callback parameters and created
      // the browser session. Accept it before attempting a second exchange.
      const initialSession = await supabase.auth.getSession();
      if (initialSession.data.session) {
        if (mounted) setReady(true);
        return;
      }

      const code = query.get("code");
      const tokenHash = query.get("token_hash");
      const type = query.get("type") as EmailOtpType | null;
      const accessToken = hash.get("access_token");
      const refreshToken = hash.get("refresh_token");

      let exchangeError: Error | null = null;
      if (code) {
        const result = await supabase.auth.exchangeCodeForSession(code);
        exchangeError = result.error;
      } else if (tokenHash && type) {
        const result = await supabase.auth.verifyOtp({ token_hash: tokenHash, type });
        exchangeError = result.error;
      } else if (accessToken && refreshToken) {
        const result = await supabase.auth.setSession({
          access_token: accessToken,
          refresh_token: refreshToken,
        });
        exchangeError = result.error;
      }

      if (exchangeError) {
        if (mounted) setError(exchangeError.message);
        return;
      }
      const { data, error: sessionError } = await supabase.auth.getSession();
      if (!mounted) return;
      if (sessionError) setError(sessionError.message);
      else if (!data.session) setError("This invitation is invalid or has expired. Ask an administrator for a new invitation.");
      else setReady(true);
    };
    const timer = window.setTimeout(() => void inspectSession(), 150);
    return () => { mounted = false; window.clearTimeout(timer); };
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (password !== confirmation) { setError("The passwords do not match."); return; }
    setBusy(true);
    setError("");
    const { error: updateError } = await getSupabaseBrowserClient().auth.updateUser({ password });
    if (updateError) setError(updateError.message);
    else setComplete(true);
    setBusy(false);
  };

  return <main className="crmLogin"><form onSubmit={submit}><div className="crmBrand"><span>WRAP</span> THEORY <small>OPS</small></div>{complete ? <><span className="kicker">ACCOUNT READY</span><h1>Password set.</h1><p>Your staff account is active. Return to the storefront and open Team CRM to sign in.</p><Link className="primary" href="/">Open storefront →</Link></> : <><span className="kicker">STAFF INVITATION</span><h1>Set your password.</h1><p>Create a strong password for your Wrap Theory operations account.</p>{!ready && !error && <p>Validating invitation…</p>}{ready && <><label>New password<input type="password" required minLength={10} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label><label>Confirm password<input type="password" required minLength={10} autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label><button className="primary" disabled={busy}>{busy ? "Saving…" : "Set password →"}</button></>}{error && <p className="formError" role="alert">{error}</p>}</>}</form></main>;
}

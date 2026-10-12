import { createClient } from "@supabase/supabase-js";

let client: ReturnType<typeof createClient> | undefined;

export function getSupabaseBrowserClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) throw new Error("Supabase frontend environment variables are not configured");
  client ??= createClient(url, key, {
    auth: { flowType: "pkce", persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  });
  return client;
}

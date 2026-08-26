import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let cachedClient: SupabaseClient | null = null;

export function getSupabaseClient(): SupabaseClient {
  if (cachedClient) {
    return cachedClient;
  }
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabasePublishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!supabaseUrl || !supabasePublishableKey) {
    throw new Error(
      "NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY are required"
    );
  }
  cachedClient = createClient(supabaseUrl, supabasePublishableKey);
  return cachedClient;
}

export async function getAccessToken(): Promise<string | null> {
  const { data } = await getSupabaseClient().auth.getSession();
  return data.session?.access_token ?? null;
}

export async function signInWithGitHub(redirectTo: string): Promise<void> {
  // Supabase's own GitHub OAuth provider, for login identity only — separate
  // from the DevStacks GitHub connector (backend /v1/connectors/github/authorize),
  // which authorizes evidence-ingestion scope and is a distinct concern.
  const { error } = await getSupabaseClient().auth.signInWithOAuth({
    provider: "github",
    options: { redirectTo },
  });
  if (error) {
    throw error;
  }
}

export async function signInWithPassword(email: string, password: string): Promise<void> {
  const { error } = await getSupabaseClient().auth.signInWithPassword({ email, password });
  if (error) {
    throw error;
  }
}

export async function signUpWithPassword(email: string, password: string): Promise<boolean> {
  const { data, error } = await getSupabaseClient().auth.signUp({ email, password });
  if (error) {
    throw error;
  }
  // Supabase returns a session immediately only when email confirmation is
  // disabled; otherwise the caller needs to tell the user to check email.
  return data.session !== null;
}

export async function signOut(): Promise<void> {
  await getSupabaseClient().auth.signOut();
}

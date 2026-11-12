import { supabase } from './supabase'

/* Redirects to Google; resolves to false only if the redirect could not start. */
export async function startGoogleSignIn(): Promise<boolean> {
  try {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/` },
    })
    return !error
  } catch {
    return false
  }
}

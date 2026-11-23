import { supabase } from './supabase'

/*
 * Redirects to Google; resolves to false only if the redirect could not start.
 * Consent is asked after sign-in, only if the profile doesn't have it yet (ConsentDialog).
 */
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

// Firebase has been removed. This stub keeps imports from breaking if any
// file still references this module.
export const isFirebaseConfigured = false

export async function signInWithGoogle(): Promise<string> {
  throw new Error('Firebase auth has been removed. Use email/password login.')
}

export async function signInFirebaseEmail(_email: string, _pass: string): Promise<string> {
  throw new Error('Firebase auth has been removed. Use email/password login.')
}

export async function registerFirebaseEmail(_email: string, _pass: string): Promise<string> {
  throw new Error('Firebase auth has been removed. Use email/password login.')
}

export async function logoutFirebase(): Promise<void> {
  // no-op
}

export const auth = null

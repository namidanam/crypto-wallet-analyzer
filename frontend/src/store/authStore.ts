import { create } from 'zustand';

export interface GoogleUser {
  googleId: string;
  email: string;
  name: string;
  picture: string;
}

interface AuthState {
  isAuthenticated: boolean;
  user: GoogleUser | null;
  token: string | null;
  loginWithGoogle: (token: string, user: GoogleUser) => void;
  logout: () => void;
  restoreSession: () => boolean;
}

const TOKEN_KEY = 'vault_auth_token';
const USER_KEY = 'vault_auth_user';

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  user: null,
  token: null,

  loginWithGoogle: (token: string, user: GoogleUser) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ isAuthenticated: true, token, user });
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({ isAuthenticated: false, token: null, user: null });
  },

  restoreSession: () => {
    const token = localStorage.getItem(TOKEN_KEY);
    const userJson = localStorage.getItem(USER_KEY);
    if (token && userJson) {
      try {
        const user = JSON.parse(userJson) as GoogleUser;
        set({ isAuthenticated: true, token, user });
        return true;
      } catch {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
      }
    }
    return false;
  },
}));

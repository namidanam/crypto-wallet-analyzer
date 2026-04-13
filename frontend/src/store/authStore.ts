import { create } from 'zustand';

// Default demo credentials
export const DEMO_CREDENTIALS = {
  username: 'vault',
  password: 'vault1234',
};

interface AuthState {
  isAuthenticated: boolean;
  vaultPassword: string | null;
  login: (username: string, password: string) => boolean;
  logout: () => void;
  checkPassword: (password: string) => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  isAuthenticated: false,
  vaultPassword: null,

  login: (username: string, password: string) => {
    // Accept demo credentials OR any custom credentials (4+ char password)
    const isDemoUser =
      username === DEMO_CREDENTIALS.username &&
      password === DEMO_CREDENTIALS.password;
    const isCustomUser = username.trim().length > 0 && password.length >= 4;

    if (isDemoUser || isCustomUser) {
      set({ isAuthenticated: true, vaultPassword: password });
      return true;
    }
    return false;
  },

  logout: () => {
    set({ isAuthenticated: false, vaultPassword: null });
  },

  checkPassword: (password: string) => {
    return get().vaultPassword === password;
  },
}));

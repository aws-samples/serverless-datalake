import { signOut as amplifySignOut } from 'aws-amplify/auth';
import { getIdToken } from '../services/auth';

// Get authentication headers for API requests
export const getAuthHeaders = async (): Promise<Record<string, string>> => {
  try {
    const idToken = await getIdToken();
    return {
      'Authorization': `Bearer ${idToken}`,
      'Content-Type': 'application/json',
    };
  } catch (error) {
    console.error('Error getting auth headers:', error);
    throw error;
  }
};

// Global function to clear authentication state
export const clearAuthState = async (): Promise<void> => {
  try {
    // Try to sign out using Amplify
    await amplifySignOut({ global: true });
  } catch (error) {
    console.log('Amplify signOut failed, clearing local storage:', error);
  }
  
  // Clear all local storage and session storage
  localStorage.clear();
  sessionStorage.clear();
  
  // Clear any cookies (basic approach)
  document.cookie.split(";").forEach((c) => {
    const eqPos = c.indexOf("=");
    const name = eqPos > -1 ? c.substr(0, eqPos) : c;
    document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/";
  });
  
  // Reload the page to ensure clean state
  window.location.reload();
};

// Make it available globally for debugging
(window as any).clearAuthState = clearAuthState;

console.log('Auth utils loaded. If you see "There is already a signed in user" error, run: clearAuthState() in the console');
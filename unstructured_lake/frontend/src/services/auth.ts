import { getCurrentUser, fetchAuthSession, signOut as amplifySignOut } from 'aws-amplify/auth';

// Get ID token (for API authentication)
export const getIdToken = async (): Promise<string> => {
  try {
    const session = await fetchAuthSession();
    const idToken = session.tokens?.idToken?.toString();
    if (!idToken) {
      throw new Error('No ID token available');
    }
    return idToken;
  } catch (error) {
    throw new Error('Failed to get valid token');
  }
};

// Check if user is authenticated
export const isAuthenticated = async (): Promise<boolean> => {
  try {
    const user = await getCurrentUser();
    return !!user;
  } catch {
    return false;
  }
};

// Sign out the current user
export const signOut = async (): Promise<void> => {
  try {
    await amplifySignOut({ global: true });
  } catch (error) {
    console.error('Error signing out:', error);
    throw error;
  }
};

// Get current user info
export const getCurrentUserInfo = async () => {
  try {
    const user = await getCurrentUser();
    return user;
  } catch (error) {
    console.error('Error getting current user:', error);
    return null;
  }
};

import { TopNavigation } from '@cloudscape-design/components';
import { useAuthenticator } from '@aws-amplify/ui-react';
import { useEffect, useState } from 'react';
import { getCurrentUserInfo, signOut as authSignOut } from '../../services/auth';

export const Header: React.FC = () => {
  const { signOut, user } = useAuthenticator();
  const [username, setUsername] = useState<string>('');

  useEffect(() => {
    const loadUserInfo = async () => {
      try {
        const userInfo = await getCurrentUserInfo();
        if (userInfo) {
          setUsername(userInfo.username || userInfo.signInDetails?.loginId || 'User');
        } else if (user) {
          setUsername(user.username || 'User');
        }
      } catch (error) {
        console.error('Error loading user info:', error);
        if (user) {
          setUsername(user.username || 'User');
        }
      }
    };

    loadUserInfo();
  }, [user]);

  const handleSignOut = async () => {
    try {
      // Try using the auth service first
      await authSignOut();
    } catch (error) {
      console.error('Error with auth service signOut, trying authenticator signOut:', error);
      try {
        // Fallback to authenticator signOut
        signOut();
      } catch (fallbackError) {
        console.error('Both signOut methods failed, using clearAuthState:', fallbackError);
        // Final fallback - use the global clear function
        if ((window as any).clearAuthState) {
          (window as any).clearAuthState();
        } else {
          // Manual cleanup
          localStorage.clear();
          sessionStorage.clear();
          window.location.reload();
        }
      }
    }
  };

  return (
    <TopNavigation
      identity={{
        href: '/',
        title: 'Document Insight Extraction',
        logo: {
          src: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIiIGhlaWdodD0iMzIiIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iNCIgZmlsbD0iIzIzMkYzRSIvPgo8cGF0aCBkPSJNOCAxMEgxNlYxMkg4VjEwWiIgZmlsbD0iI0ZGRkZGRiIvPgo8cGF0aCBkPSJNOCAxNUgyNFYxN0g4VjE1WiIgZmlsbD0iI0ZGRkZGRiIvPgo8cGF0aCBkPSJNOCAyMEgyNFYyMkg4VjIwWiIgZmlsbD0iI0ZGRkZGRiIvPgo8L3N2Zz4K',
          alt: 'Document Insight Extraction',
        },
      }}
      utilities={[
        {
          type: 'button',
          text: 'Documentation',
          href: 'https://docs.aws.amazon.com',
          external: true,
          externalIconAriaLabel: ' (opens in a new tab)',
        },
        {
          type: 'menu-dropdown',
          text: username || 'User',
          description: username,
          iconName: 'user-profile',
          items: [
            {
              id: 'signout',
              text: 'Sign out',
            },
          ],
          onItemClick: ({ detail }) => {
            if (detail.id === 'signout') {
              handleSignOut();
            }
          },
        },
      ]}
      i18nStrings={{
        searchIconAriaLabel: 'Search',
        searchDismissIconAriaLabel: 'Close search',
        overflowMenuTriggerText: 'More',
        overflowMenuTitleText: 'All',
        overflowMenuBackIconAriaLabel: 'Back',
        overflowMenuDismissIconAriaLabel: 'Close menu',
      }}
    />
  );
};

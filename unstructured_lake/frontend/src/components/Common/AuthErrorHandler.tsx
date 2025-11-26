import { Button, Container, Header, SpaceBetween } from '@cloudscape-design/components';
import { signOut } from '../../services/auth';

interface AuthErrorHandlerProps {
  error?: string;
}

export const AuthErrorHandler: React.FC<AuthErrorHandlerProps> = ({ error }) => {
  const handleSignOut = async () => {
    try {
      await signOut();
      // Force page reload to clear any cached auth state
      window.location.reload();
    } catch (error) {
      console.error('Error signing out:', error);
      // Force page reload anyway to clear state
      window.location.reload();
    }
  };

  if (!error || !error.includes('already a signed in user')) {
    return null;
  }

  return (
    <Container>
      <SpaceBetween size="m">
        <Header variant="h2">Authentication Issue</Header>
        <p>
          There appears to be an existing authentication session. 
          Please sign out to continue with a fresh login.
        </p>
        <Button variant="primary" onClick={handleSignOut}>
          Sign Out and Refresh
        </Button>
      </SpaceBetween>
    </Container>
  );
};
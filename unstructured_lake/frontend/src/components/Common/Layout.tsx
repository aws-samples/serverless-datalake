import { AppLayout, SideNavigation } from '@cloudscape-design/components';
import { useNavigate, useLocation } from 'react-router-dom';
import { Header } from './Header';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    {
      type: 'link' as const,
      text: 'Home',
      href: '/',
    },
    {
      type: 'link' as const,
      text: 'Extract Insights',
      href: '/insights',
    },
    {
      type: 'link' as const,
      text: 'Image Insights',
      href: '/image-insights',
    },
  ];

  return (
    <>
      <Header />
      <AppLayout
        navigation={
          <SideNavigation
            activeHref={location.pathname}
            header={{
              href: '/',
              text: 'Navigation',
            }}
            items={navItems}
            onFollow={(event) => {
              event.preventDefault();
              navigate(event.detail.href);
            }}
          />
        }
        content={children}
        toolsHide
        navigationWidth={200}
      />
    </>
  );
};

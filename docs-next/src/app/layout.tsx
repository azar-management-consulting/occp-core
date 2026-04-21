import type { Viewport } from 'next';
import './global.css';

/**
 * Root layout — minimal. Real <html>/<body>/metadata lives under
 * `src/app/[lang]/layout.tsx` where we know the active language.
 */
export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0a0a0a' },
  ],
  colorScheme: 'dark light',
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

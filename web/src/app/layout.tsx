import type { Metadata, Viewport } from 'next';
import './globals.css';
import { BottomNav } from '@/components/BottomNav';

export const metadata: Metadata = {
  title: 'KeibaAI — 競馬予想',
  description: '展開シナリオ別の確率予測と期待値ベースの買い目推奨',
  manifest: '/manifest.webmanifest',
  appleWebApp: { capable: true, statusBarStyle: 'black-translucent', title: 'KeibaAI' },
  icons: {
    icon: [{ url: '/icon-192.svg', type: 'image/svg+xml' }],
    apple: '/icon-192.svg',
  },
};

export const viewport: Viewport = {
  themeColor: '#0b0d16',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  viewportFit: 'cover',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja" className="dark" data-theme="dark">
      <body className="min-h-dvh pb-20">
        <main className="max-w-lg mx-auto">{children}</main>
        <BottomNav />
      </body>
    </html>
  );
}

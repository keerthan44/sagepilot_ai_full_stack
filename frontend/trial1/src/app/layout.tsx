import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Link from 'next/link';
import '../../styles/globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  title: 'Voice AI',
  description: 'Voice AI agent powered by LiveKit',
};

interface RootLayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <body className="bg-background text-foreground min-h-screen font-sans antialiased">
        <header className="border-border bg-background/80 sticky top-0 z-40 border-b backdrop-blur-sm">
          <nav className="mx-auto flex max-w-4xl items-center justify-between px-6 py-3">
            <Link href="/" className="text-sm font-semibold tracking-tight hover:opacity-80">
              Voice AI
            </Link>
            <div className="flex items-center gap-6">
              <Link
                href="/"
                className="text-muted-foreground hover:text-foreground text-sm transition-colors"
              >
                Home
              </Link>
              <Link
                href="/sessions"
                className="text-muted-foreground hover:text-foreground text-sm transition-colors"
              >
                Sessions
              </Link>
            </div>
          </nav>
        </header>
        <main className="mx-auto max-w-4xl px-6 py-10">{children}</main>
      </body>
    </html>
  );
}

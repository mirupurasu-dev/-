'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, BarChart3, Wallet, Settings } from 'lucide-react';
import { cn } from '@/lib/cn';

const items = [
  { href: '/', label: 'ホーム', icon: Home },
  { href: '/analyze', label: '分析', icon: BarChart3 },
  { href: '/bankroll', label: '資金', icon: Wallet },
  { href: '/settings', label: '設定', icon: Settings },
];

export function BottomNav() {
  const path = usePathname();
  return (
    <nav className="fixed bottom-0 inset-x-0 z-40 border-t border-border bg-card/80 backdrop-blur-lg safe-bottom">
      <ul className="grid grid-cols-4 max-w-lg mx-auto">
        {items.map((item) => {
          const Icon = item.icon;
          const active = path === item.href;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={cn(
                  'flex flex-col items-center gap-0.5 py-2.5 text-[10px] transition-colors',
                  active ? 'text-accent' : 'text-muted-fg hover:text-fg'
                )}
              >
                <Icon size={20} strokeWidth={active ? 2.2 : 1.8} />
                <span>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

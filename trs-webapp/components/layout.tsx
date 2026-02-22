'use client';

import { useEffect, useState, Suspense } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Navbar } from './navbar';
import { AlertContainer, Alert } from './alert';
import { getCurrentUser } from '@/lib/api';
import { User } from '@/lib/types';

function LayoutContent({ children }: { children: React.ReactNode }) {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    getCurrentUser().then(setCurrentUser);
  }, [pathname]);

  useEffect(() => {
    const message = searchParams.get('message');
    const category = searchParams.get('category') as Alert['category'] | null;
    
    if (message && category) {
      addAlert({ category, message });
      const newParams = new URLSearchParams(searchParams);
      newParams.delete('message');
      newParams.delete('category');
      router.replace(pathname + (newParams.toString() ? '?' + newParams.toString() : ''));
    }
  }, [searchParams, pathname, router]);

  const addAlert = (alert: Omit<Alert, 'id'>) => {
    const id = Math.random().toString(36).substring(7);
    setAlerts((prev) => [...prev, { ...alert, id }]);
  };

  const dismissAlert = (id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar currentUser={currentUser} />
      <main className="container mx-auto px-4 py-8">
        <AlertContainer alerts={alerts} onDismiss={dismissAlert} />
        {children}
      </main>
    </div>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-50">
        <div className="container mx-auto px-4 py-8">
          {children}
        </div>
      </div>
    }>
      <LayoutContent>{children}</LayoutContent>
    </Suspense>
  );
}

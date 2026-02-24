'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { logout } from '@/lib/api';
import { User } from '@/lib/types';

interface NavbarProps {
  currentUser: User | null;
}

export function Navbar({ currentUser }: NavbarProps) {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push('/');
    router.refresh();
  };

  const isActive = (path: string) => pathname === path || pathname.startsWith(path + '/');

  return (
    <nav className="bg-gray-900 text-white">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-6">
            <Link href="/" className="font-semibold text-lg">
              TRS
            </Link>
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className={`px-3 py-2 rounded-md text-sm font-medium ${isActive('/') ? 'bg-gray-800' : 'hover:bg-gray-800'
                  }`}
              >
                Home
              </Link>
              <Link
                href="/users"
                className={`px-3 py-2 rounded-md text-sm font-medium ${isActive('/users') ? 'bg-gray-800' : 'hover:bg-gray-800'
                  }`}
              >
                Users
              </Link>
              <Link
                href="/lobbies"
                className={`px-3 py-2 rounded-md text-sm font-medium ${isActive('/lobbies') ? 'bg-gray-800' : 'hover:bg-gray-800'
                  }`}
              >
                Lobbies
              </Link>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {currentUser ? (
              <>
                <Link href={`/users/${currentUser.id}`}>
                  <Button variant="ghost" size="sm">
                    My profile
                  </Button>
                </Link>
                <Button variant="outline" size="sm" onClick={handleLogout}>
                  Logout ({currentUser.name})
                </Button>
              </>
            ) : (
              <>
                <Link href="/register">
                  <Button variant="outline" size="sm">Register</Button>
                </Link>
                <Link href="/login">
                  <Button size="sm">Login</Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

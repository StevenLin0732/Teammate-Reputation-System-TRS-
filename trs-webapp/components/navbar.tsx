"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/api";
import { User } from "@/lib/types";
import {
  EnvelopeIcon,
  GraphIcon,
  PaperPlaneIcon,
  PlusCircleIcon,
  StorefrontIcon,
  User,
  UsersFourIcon,
} from "@phosphor-icons/react";
import { UserCircleIcon } from "@phosphor-icons/react/dist/ssr";

interface NavbarProps {
  currentUser: User | null;
}

export function Navbar({ currentUser }: NavbarProps) {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push("/");
    router.refresh();
  };

  const isActive = (path: string) =>
    pathname === path || pathname.startsWith(path + "/");

  return (
    <nav className="bg-gray-900 text-white">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-6">
            {/* <Link href="/" className="font-semibold text-lg"> */}
            {/*   TRS */}
            {/* </Link> */}
            <div className="flex flex-row items-center gap-0 md:gap-2">
              <Link
                href="/"
                className={`pr-3 pl-2 py-2 rounded-md text-xl font-semibold ${isActive("/") ? "bg-gray-800" : "hover:bg-gray-800"
                  }`}
              >
                TRS
              </Link>
              <Link
                href="/users"
                className={`px-3 py-2 rounded-md text-sm font-medium ${isActive("/users") ? "bg-gray-800" : "hover:bg-gray-800"
                  }`}
              >
                <span className="flex gap-1 items-center">
                  <UserCircleIcon className="text-2xl" />
                  <span className="hidden sm:block">Users</span>
                </span>
              </Link>
              <Link
                href="/lobbies"
                className={`px-3 py-2 rounded-md text-sm font-medium ${isActive("/lobbies") ? "bg-gray-800" : "hover:bg-gray-800"
                  }`}
              >
                <span className="flex gap-1 items-center">
                  <StorefrontIcon className="text-2xl" />
                  <span className="hidden sm:block">Lobbies</span>
                </span>
              </Link>
              <Link
                href="/graph"
                className={`px-3 py-2 rounded-md text-sm font-medium ${isActive("/graph") ? "bg-gray-800" : "hover:bg-gray-800"
                  }`}
              >
                <span className="flex gap-1 items-center">
                  <GraphIcon className="text-2xl" />
                  <span className="hidden sm:block">Graph</span>
                </span>
              </Link>
              {currentUser && (
                <>
                  <Link
                    href="/join-requests"
                    className={`flex items-center gap-x-1 py-2 px-1 rounded-md text-sm font-medium ${isActive("/join-requests")
                        ? "bg-gray-800"
                        : "hover:bg-gray-800"
                      }`}
                  >
                    <PaperPlaneIcon className="text-2xl" />
                    Join Requests
                  </Link>
                  <Link
                    href="/invites"
                    className={` flex items-center gap-x-1 py-2 px-1 rounded-md text-sm font-medium ${isActive("/invites") ? "bg-gray-800" : "hover:bg-gray-800"
                      }`}
                  >
                    <EnvelopeIcon className="text-2xl" />
                    Invites
                  </Link>
                </>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
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
                  <Button variant="outline" size="sm">
                    <PlusCircleIcon className="sm:hidden text-2xl" />
                    Register
                  </Button>
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

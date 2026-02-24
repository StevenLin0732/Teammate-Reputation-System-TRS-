'use client';

import { Suspense, useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { login, getCurrentUser } from '@/lib/api';
import { toast } from 'sonner';

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
      // fetch current user to greet by first name
      const user = await getCurrentUser();
      const firstName = user && user.name ? user.name.split(' ')[0] : null;
      if (firstName) {
        toast.success(`Welcome back, ${firstName}!`);
      } else {
        toast.success('Logged in successfully');
      }

      const next = searchParams.get('next') || '/me';
      router.push(next);
    } catch (err) {
      setError('Invalid credentials. Please try again.');
      toast.error('Login failed. Check your email and password.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const user = await getCurrentUser();
        if (!mounted) return;
        if (user) {
          router.push('/me');
          return;
        }
      } catch (err) {
        // ignore
      } finally {
        if (!mounted) return;
        setCheckingAuth(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [router]);

  return (
    checkingAuth ? (
      <div className="flex justify-center">
        <div className="w-full max-w-md">Checking authentication...</div>
      </div>
    ) : (
      <div className="flex justify-center">
        <div className="w-full max-w-md">
          <Card>
            <CardHeader>
              <CardTitle>Login</CardTitle>
              <CardDescription>Enter your credentials to access your account.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="Enter your email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
                {error && (
                  <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
                    {error}
                  </div>
                )}
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? 'Logging in...' : 'Login'}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  )
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center">
          <div className="w-full max-w-md">Loading...</div>
        </div>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}

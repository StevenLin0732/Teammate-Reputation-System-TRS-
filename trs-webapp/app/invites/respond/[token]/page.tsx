'use client';

import { Suspense, use, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

function InviteRespondPageContent({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const action = searchParams.get('action');
  const [loading, setLoading] = useState(false);
  const { token } = use(params);

  useEffect(() => {
    if (action === 'accept' || action === 'reject') {
      handleRespond(action);
    }
  }, [action]);

  const handleRespond = async (respondAction: string) => {
    setLoading(true);
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:5000';
      const response = await fetch(
        `${API_BASE}/invites/respond/${token}?action=${respondAction}`,
        {
          credentials: 'include',
        }
      );
      if (response.ok || response.status === 302) {
        const location = response.headers.get('location');
        if (location) {
          const lobbyId = location.match(/\/lobbies\/(\d+)/)?.[1];
          if (lobbyId) {
            router.push(`/lobbies/${lobbyId}`);
          } else {
            router.push('/lobbies');
          }
        } else {
          router.push('/lobbies');
        }
      }
    } catch (err) {
      console.error('Failed to respond to invitation', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[400px]">
        <div>Processing invitation...</div>
      </div>
    );
  }

  return (
    <div className="flex justify-center">
      <div className="w-full max-w-md">
        <Card>
          <CardHeader>
            <CardTitle>Invitation</CardTitle>
            <CardDescription>
              Click below to accept or reject the team invitation.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex gap-2">
            <Button
              onClick={() => handleRespond('accept')}
              className="flex-1"
              disabled={loading}
            >
              Accept
            </Button>
            <Button
              onClick={() => handleRespond('reject')}
              variant="outline"
              className="flex-1"
              disabled={loading}
            >
              Reject
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function InviteRespondPage(props: {
  params: Promise<{ token: string }>;
}) {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center items-center min-h-[400px]">
          <div>Loading invitation...</div>
        </div>
      }
    >
      <InviteRespondPageContent {...props} />
    </Suspense>
  );
}

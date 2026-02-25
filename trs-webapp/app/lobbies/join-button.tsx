'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { createJoinRequest, getCurrentUser } from '@/lib/api';
import { toast } from 'sonner';

export function JoinLobbyButton({
  lobbyId,
  requestStatus,
}: {
  lobbyId: number;
  requestStatus?: string;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const handleJoin = async () => {
    setLoading(true);
    try {
      const user = await getCurrentUser();
      if (!user) {
        router.push(`/login?next=/lobbies/${lobbyId}`);
        return;
      }
      await createJoinRequest(lobbyId);
      toast.success('Join request submitted!');
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to submit join request';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  if (requestStatus === 'pending') {
    return (
      <Button variant="outline" size="sm" disabled>
        Requested
      </Button>
    );
  }

  return (
    <Button variant="outline" size="sm" onClick={handleJoin} disabled={loading}>
      {loading ? 'Requesting...' : 'Request to join'}
    </Button>
  );
}

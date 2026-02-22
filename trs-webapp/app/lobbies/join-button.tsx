'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { joinLobby, getCurrentUser } from '@/lib/api';

export function JoinLobbyButton({ lobbyId }: { lobbyId: number }) {
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
      await joinLobby(lobbyId, user.id);
      router.refresh();
    } catch (err) {
      alert('Failed to join lobby');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button variant="outline" size="sm" onClick={handleJoin} disabled={loading}>
      {loading ? 'Joining...' : 'Join'}
    </Button>
  );
}

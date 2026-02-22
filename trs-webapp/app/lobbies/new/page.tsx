'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { createLobby, getCurrentUser } from '@/lib/api';

export default function CreateLobbyPage() {
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [contestLink, setContestLink] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (!title.trim()) {
      setError('Title is required');
      setLoading(false);
      return;
    }

    try {
      const user = await getCurrentUser();
      if (!user) {
        router.push('/login?next=/lobbies/new');
        return;
      }
      await createLobby({
        title: title.trim(),
        contest_link: contestLink.trim() || undefined,
        leader_id: user.id,
      });
      router.push('/lobbies');
    } catch (err) {
      setError('Failed to create lobby. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex justify-center">
      <div className="w-full max-w-2xl">
        <div className="flex items-end justify-between mb-4">
          <div>
            <h1 className="text-2xl font-semibold mb-1">Create a lobby</h1>
            <div className="text-muted-foreground">Start recruiting for a contest or project.</div>
          </div>
          <Link href="/lobbies">
            <Button variant="outline" size="sm">
              Back
            </Button>
          </Link>
        </div>

        <Card>
          <CardContent className="pt-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g., ICPC Regional 2026 Team"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="contest_link">Contest link (optional)</Label>
                <Input
                  id="contest_link"
                  value={contestLink}
                  onChange={(e) => setContestLink(e.target.value)}
                  placeholder="https://..."
                />
              </div>
              {error && (
                <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
                  {error}
                </div>
              )}
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? 'Creating...' : 'Create lobby'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

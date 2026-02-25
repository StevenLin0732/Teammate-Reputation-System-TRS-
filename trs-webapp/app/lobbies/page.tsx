import Link from 'next/link';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getLobbies, getCurrentUser } from '@/lib/api';
import { Lobby } from '@/lib/types';
import { JoinLobbyButton } from './join-button';

export const dynamic = 'force-dynamic';

export default async function LobbiesPage() {
  const [lobbies, currentUser] = await Promise.all([
    getLobbies(),
    getCurrentUser(),
  ]);

  return (
    <>
      <div className="flex items-end justify-between gap-3 mb-4">
        <div>
          <h1 className="text-2xl font-semibold mb-1">Lobbies</h1>
          <div className="text-muted-foreground">Browse active lobbies and contest links.</div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{lobbies.length} total</Badge>
          {currentUser && (
            <Link href="/lobbies/new">
              <Button size="sm">Create lobby</Button>
            </Link>
          )}
        </div>
      </div>

      {lobbies.length === 0 ? (
        <Card>
          <CardContent className="py-8">
            <div className="text-center text-muted-foreground">
              No lobbies found. Run the seed script to populate the DB.
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {lobbies.map((lobby) => (
            <Card key={lobby.id}>
              <CardHeader>
                <div className="flex justify-between items-start gap-2">
                  <CardTitle className="mb-1">{lobby.title}</CardTitle>
                  <div className="flex gap-1 flex-wrap justify-end">
                    <Badge variant="default">{lobby.participant_count || 0} members</Badge>
                    {lobby.team_reputation !== undefined && (
                      <Badge variant="secondary">Team Rep {lobby.team_reputation.toFixed(1)}</Badge>
                    )}
                    {lobby.finished && <Badge variant="outline">Finished</Badge>}
                    {lobby.team_locked && !lobby.finished && (
                      <Badge variant="outline">Locked</Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {lobby.contest_link && (
                  <div className="text-sm mb-3">
                    <a
                      href={lobby.contest_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      {lobby.contest_link}
                    </a>
                  </div>
                )}
                <div className="flex gap-2 flex-wrap">
                  <Link href={`/lobbies/${lobby.id}`}>
                    <Button variant="outline" size="sm">
                      Open
                    </Button>
                  </Link>
                  {currentUser && (
                    <>
                      {lobby.role && (
                        <Button variant="secondary" size="sm" disabled>
                          {lobby.role}
                        </Button>
                      )}
                      {!lobby.role && !lobby.finished && !lobby.team_locked && (
                        <JoinLobbyButton
                          lobbyId={lobby.id}
                          requestStatus={lobby.join_request_status}
                        />
                      )}
                    </>
                  )}
                </div>
              </CardContent>
              <CardFooter className="pt-0">
                <div className="text-sm text-muted-foreground">Lobby ID: {lobby.id}</div>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

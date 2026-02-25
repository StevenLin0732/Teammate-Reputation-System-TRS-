'use client';

import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { getLobby, getCurrentUser, getUser, getJoinRequests, decideJoinRequest, createJoinRequest } from '@/lib/api';
import { Lobby, User } from '@/lib/types';
import type { JoinRequest } from '@/lib/api';
import { toast } from 'sonner';

const API_BASE = typeof window !== 'undefined'
  ? (process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:5000')
  : 'http://localhost:5000';

export default function LobbyDetailPage({
  params,
}: {
  params: Promise<{ lobbyId: string }>;
}) {
  const router = useRouter();
  const { lobbyId: lobbyIdParam } = use(params);
  const lobbyId = Number.parseInt(lobbyIdParam, 10);
  const [lobby, setLobby] = useState<Lobby | null>(null);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [leader, setLeader] = useState<User | null>(null);
  const [members, setMembers] = useState<User[]>([]);
  const [joinRequests, setJoinRequests] = useState<JoinRequest[]>([]);
  const [joinRequestUsers, setJoinRequestUsers] = useState<Map<number, User>>(new Map());
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [lobbyData, user] = await Promise.all([
          getLobby(lobbyId),
          getCurrentUser(),
        ]);
        setLobby(lobbyData);
        setCurrentUser(user);

        if (lobbyData.leader_id) {
          try {
            const leaderData = await getUser(lobbyData.leader_id);
            setLeader(leaderData);
          } catch { }
        }

        if (lobbyData.participants && lobbyData.participants.length > 0) {
          const memberData = await Promise.all(
            lobbyData.participants.map((p: any) => getUser(p.id).catch(() => null))
          );
          setMembers(memberData.filter(Boolean) as User[]);
          if (memberData.length > 0 && user) {
            const teammates = memberData.filter((m: User | null) => m && m.id !== user.id);
            if (teammates.length > 0) {
              setActiveTab(teammates[0]!.id.toString());
            }
          }
        }

        // Load join requests if user is the leader
        if (user && lobbyData.leader_id === user.id) {
          try {
            const requests = await getJoinRequests(lobbyId, 'pending');
            setJoinRequests(requests);

            // Load user data for each request
            const userMap = new Map<number, User>();
            for (const req of requests) {
              try {
                const userData = await getUser(req.requester_id);
                userMap.set(req.requester_id, userData);
              } catch { }
            }
            setJoinRequestUsers(userMap);
          } catch (err) {
            console.error('Failed to load join requests', err);
          }
        }
      } catch (err) {
        console.error('Failed to load lobby data', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [lobbyId]);

  const isLeader = currentUser?.id === lobby?.leader_id;
  const isMember = members.some(m => m.id === currentUser?.id);
  const teammates = members.filter(m => m.id !== currentUser?.id);

  const handleFormSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const formData = new FormData(form);

    try {
      const response = await fetch(form.action, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      if (response.ok || response.status === 302) {
        router.refresh();
        window.location.reload();
      }
    } catch (err) {
      console.error('Form submission failed', err);
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!lobby) {
    return <div>Lobby not found</div>;
  }

  return (
    <>
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h1 className="text-2xl font-semibold mb-1">{lobby.title}</h1>
          <div className="text-muted-foreground flex items-center gap-2">
            Lobby ID: {lobby.id}
            {lobby.finished && <Badge variant="outline">Finished</Badge>}
            {lobby.team_locked && !lobby.finished && <Badge variant="outline">Locked</Badge>}
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Link href="/lobbies">
            <Button variant="outline" size="sm">
              Back to lobbies
            </Button>
          </Link>
          {currentUser && !isMember && !lobby.finished && !lobby.team_locked && (
            <Button
              size="sm"
              onClick={async () => {
                try {
                  await createJoinRequest(lobbyId);
                  toast.success('Join request submitted!');
                  router.refresh();
                } catch (err) {
                  const message = err instanceof Error ? err.message : 'Failed to submit request';
                  toast.error(message);
                }
              }}
            >
              Request to join
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm uppercase text-muted-foreground">Contest</CardTitle>
            </CardHeader>
            <CardContent>
              {lobby.contest_link ? (
                <a
                  href={lobby.contest_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  {lobby.contest_link}
                </a>
              ) : (
                <div className="text-muted-foreground">No contest link provided.</div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm uppercase text-muted-foreground">Leader</CardTitle>
            </CardHeader>
            <CardContent>
              {leader ? (
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="font-semibold">{leader.name}</div>
                    <div className="text-sm text-muted-foreground">User ID: {leader.id}</div>
                  </div>
                  <Link href={`/users/${leader.id}`}>
                    <Button variant="outline" size="sm">
                      View profile
                    </Button>
                  </Link>
                </div>
              ) : (
                <div className="text-muted-foreground">No leader assigned.</div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm uppercase text-muted-foreground">Members</CardTitle>
            </CardHeader>
            <CardContent>
              {members.length > 0 ? (
                <div className="space-y-2">
                  {members.map((member) => (
                    <div
                      key={member.id}
                      className="flex items-center justify-between gap-2 py-2 border-b last:border-0"
                    >
                      <div>
                        <div className="font-semibold">{member.name}</div>
                        <div className="text-sm text-muted-foreground">
                          {member.major || '—'}
                          {member.year && ` · ${member.year}`}
                        </div>
                      </div>
                      <Link href={`/users/${member.id}`}>
                        <Button variant="outline" size="sm">
                          Profile
                        </Button>
                      </Link>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-muted-foreground">No members yet.</div>
              )}

              {currentUser && isMember && !lobby.team_locked && !lobby.finished && (
                <>
                  <hr className="my-4" />
                  <form
                    action={`${API_BASE}/lobbies/${lobbyId}/invite`}
                    method="post"
                    onSubmit={handleFormSubmit}
                    className="space-y-2"
                  >
                    <Input
                      name="target_email"
                      placeholder="Invite user by email (@duke.edu)"
                      required
                      className="text-sm"
                    />
                    <Button type="submit" size="sm" variant="outline" className="w-full">
                      Request teammate
                    </Button>
                  </form>
                </>
              )}
            </CardContent>
          </Card>

          {isLeader && joinRequests.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm uppercase text-muted-foreground">Join Requests</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {joinRequests.map((request) => {
                    const requester = joinRequestUsers.get(request.requester_id);
                    return (
                      <div
                        key={request.id}
                        className="flex items-center justify-between p-3 border rounded-lg"
                      >
                        <div>
                          <div className="font-semibold">{requester?.name || 'Unknown User'}</div>
                          <div className="text-sm text-muted-foreground">
                            Status: <Badge variant="outline">{request.status}</Badge>
                          </div>
                        </div>
                        {request.status === 'pending' && !lobby.team_locked && (
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              onClick={async () => {
                                try {
                                  await decideJoinRequest(lobbyId, request.id, 'accept');
                                  toast.success('Request accepted!');
                                  router.refresh();
                                } catch (err) {
                                  const message = err instanceof Error ? err.message : 'Failed to accept';
                                  toast.error(message);
                                }
                              }}
                            >
                              Accept
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={async () => {
                                try {
                                  await decideJoinRequest(lobbyId, request.id, 'reject');
                                  toast.success('Request rejected');
                                  router.refresh();
                                } catch (err) {
                                  const message = err instanceof Error ? err.message : 'Failed to reject';
                                  toast.error(message);
                                }
                              }}
                            >
                              Reject
                            </Button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        <div className="lg:col-span-3 space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Lobby details</CardTitle>
                {isLeader && <Badge variant="default">Leader</Badge>}
              </div>
            </CardHeader>
            <CardContent>
              <form
                action={`${API_BASE}/lobbies/${lobbyId}`}
                method="post"
                onSubmit={handleFormSubmit}
                className="space-y-4"
              >
                <input type="hidden" name="action" value="save" />
                <fieldset disabled={!isLeader} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="title">Title</Label>
                    <Input
                      id="title"
                      name="title"
                      defaultValue={lobby.title}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="contest_link">Contest link</Label>
                    <Input
                      id="contest_link"
                      name="contest_link"
                      defaultValue={lobby.contest_link || ''}
                      placeholder="https://..."
                    />
                  </div>
                </fieldset>
                {isLeader && (
                  <div className="flex justify-end gap-2">
                    <Button type="submit">Save changes</Button>
                  </div>
                )}
              </form>

              {isLeader && !lobby.team_locked && (
                <form
                  action={`${API_BASE}/lobbies/${lobbyId}`}
                  method="post"
                  onSubmit={handleFormSubmit}
                  className="mt-2"
                >
                  <input type="hidden" name="action" value="lock_team" />
                  <Button type="submit" variant="outline">
                    Lock team
                  </Button>
                </form>
              )}

              {isLeader && !lobby.finished && (
                <form
                  action={`${API_BASE}/lobbies/${lobbyId}`}
                  method="post"
                  onSubmit={handleFormSubmit}
                  className="mt-2"
                >
                  <input type="hidden" name="action" value="finish_contest" />
                  <Button type="submit" variant="outline">
                    Mark contest as finished
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>

          {lobby.finished && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Proof submissions</CardTitle>
                </CardHeader>
                <CardContent>
                  {currentUser && isMember ? (
                    <>
                      <p className="text-muted-foreground mb-3">Verify your participation.</p>
                      <form
                        action={`${API_BASE}/lobbies/${lobbyId}/submit`}
                        method="post"
                        onSubmit={handleFormSubmit}
                        className="space-y-2"
                      >
                        <div className="space-y-2">
                          <Label htmlFor="proof">Proof link / notes</Label>
                          <Input
                            id="proof"
                            name="proof"
                            placeholder="https://... or a short description"
                            required
                          />
                        </div>
                        <div className="flex justify-end">
                          <Button type="submit">Submit proof</Button>
                        </div>
                      </form>
                      <hr className="my-4" />
                    </>
                  ) : (
                    <p className="text-muted-foreground mb-3">Verify contest legitimacy.</p>
                  )}
                  <div className="text-muted-foreground">No proofs submitted yet.</div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Rate teammates</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">
                    Pick a teammate on the left; update/delete your rating anytime.
                  </p>
                </CardHeader>
                <CardContent>
                  {currentUser && isMember && teammates.length > 0 ? (
                    <div className="grid grid-cols-5 gap-4">
                      <div className="col-span-2 space-y-2">
                        {teammates.map((teammate, idx) => (
                          <button
                            key={teammate.id}
                            onClick={() => setActiveTab(teammate.id.toString())}
                            className={`w-full text-left p-2 rounded-lg border ${activeTab === teammate.id.toString()
                                ? 'border-green-500 bg-green-50'
                                : 'border-gray-200'
                              }`}
                          >
                            <div className="flex justify-between items-center">
                              <span className="font-semibold">{teammate.name}</span>
                              <Badge variant="secondary" className="text-xs">
                                New
                              </Badge>
                            </div>
                          </button>
                        ))}
                      </div>
                      <div className="col-span-3">
                        {activeTab && teammates.find(t => t.id.toString() === activeTab) && (
                          <RatingForm
                            lobbyId={lobbyId}
                            teammate={teammates.find(t => t.id.toString() === activeTab)!}
                            onSubmit={handleFormSubmit}
                          />
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="text-muted-foreground">
                      Log in as a team member to rate teammates.
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Ratings matrix</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">
                    Rows are receivers; columns are raters. Values are{' '}
                    <span className="text-green-600 font-semibold">contribution</span>/
                    <span className="text-blue-600 font-semibold">communication</span>.
                  </p>
                </CardHeader>
                <CardContent>
                  {members.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm border-collapse border border-gray-300 text-center">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="border border-gray-300 p-2 text-left">Receiver</th>
                            {members.map((rater) => (
                              <th key={rater.id} className="border border-gray-300 p-2">
                                {rater.name}
                              </th>
                            ))}
                            <th className="border border-gray-300 p-2">Avg</th>
                          </tr>
                        </thead>
                        <tbody>
                          {members.map((receiver) => (
                            <tr key={receiver.id}>
                              <th className="border border-gray-300 p-2 text-left">
                                {receiver.name}
                              </th>
                              {members.map((rater) => (
                                <td key={rater.id} className="border border-gray-300 p-2">
                                  {receiver.id === rater.id ? (
                                    <span className="text-muted-foreground">—</span>
                                  ) : (
                                    <span className="text-muted-foreground">—</span>
                                  )}
                                </td>
                              ))}
                              <td className="border border-gray-300 p-2">
                                <span className="text-muted-foreground">—</span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-muted-foreground">No ratings yet.</div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </>
  );
}

function RatingForm({
  lobbyId,
  teammate,
  onSubmit,
}: {
  lobbyId: number;
  teammate: User;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <form
      action={`${API_BASE}/lobbies/${lobbyId}/rate`}
      method="post"
      onSubmit={onSubmit}
      className="space-y-3"
    >
      <input type="hidden" name="target_user_id" value={teammate.id} />
      <div className="space-y-2">
        <Label htmlFor={`contribution-${teammate.id}`}>Contribution</Label>
        <Input
          id={`contribution-${teammate.id}`}
          name="contribution"
          type="number"
          min="0"
          max="10"
          defaultValue="8"
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor={`communication-${teammate.id}`}>Communication</Label>
        <Input
          id={`communication-${teammate.id}`}
          name="communication"
          type="number"
          min="0"
          max="10"
          defaultValue="8"
          required
        />
      </div>
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id={`would-${teammate.id}`}
          name="would_work_again"
          className="w-4 h-4"
        />
        <Label htmlFor={`would-${teammate.id}`} className="cursor-pointer">
          Would work again
        </Label>
      </div>
      <div className="space-y-2">
        <Label htmlFor={`comment-${teammate.id}`}>Comment</Label>
        <Textarea
          id={`comment-${teammate.id}`}
          name="comment"
          rows={3}
          placeholder="Short feedback…"
        />
      </div>
      <div className="flex justify-end">
        <Button type="submit">Save</Button>
      </div>
    </form>
  );
}

'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getCurrentUser, getLobby, getUser } from '@/lib/api';
import type { Invitation } from '@/lib/types';
import type { User, Lobby } from '@/lib/types';

interface InvitationWithDetails {
    invitation: Invitation;
    lobby?: Lobby;
    user?: User;
}

export default function InvitesPage() {
    const router = useRouter();
    const [currentUser, setCurrentUser] = useState<User | null>(null);
    const [received, setReceived] = useState<InvitationWithDetails[]>([]);
    const [sent, setSent] = useState<InvitationWithDetails[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function loadData() {
            try {
                const user = await getCurrentUser();
                if (!user) {
                    router.push('/login?next=/invites');
                    return;
                }

                setCurrentUser(user);
                // TODO: Fetch invitations from API when endpoint is available
                // For now, show informational page
                setLoading(false);
            } catch (err) {
                setLoading(false);
            }
        }

        loadData();
    }, [router]);

    if (loading) {
        return <div className="text-center py-12">Loading...</div>;
    }

    return (
        <>
            <div className="flex items-end justify-between gap-3 mb-4">
                <div>
                    <h1 className="text-2xl font-semibold mb-1">Invitations</h1>
                    <div className="text-muted-foreground">
                        Manage team invitations you've received and sent.
                    </div>
                </div>
            </div>

            <div className="grid gap-4">
                {/* Received Invitations */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Invitations Received</CardTitle>
                        <CardDescription>Join invitations from team leaders</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {received.length === 0 ? (
                            <div className="text-muted-foreground py-4">
                                You haven't received any invitations yet.
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {received.map((item) => (
                                    <div
                                        key={item.invitation.id}
                                        className="flex items-center justify-between p-3 border rounded-lg"
                                    >
                                        <div>
                                            <div className="font-semibold">{item.lobby?.title}</div>
                                            <div className="text-sm text-muted-foreground">
                                                From {item.user?.name} · Status:{' '}
                                                <Badge variant="outline">{item.invitation.status}</Badge>
                                            </div>
                                        </div>
                                        {item.invitation.status === 'pending' && (
                                            <div className="flex gap-2">
                                                <Link href={`/invites/respond/${item.invitation.token}?action=accept`}>
                                                    <Button size="sm">Accept</Button>
                                                </Link>
                                                <Link href={`/invites/respond/${item.invitation.token}?action=reject`}>
                                                    <Button variant="outline" size="sm">Reject</Button>
                                                </Link>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Sent Invitations */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Invitations Sent</CardTitle>
                        <CardDescription>Join invitations you've sent to users</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {sent.length === 0 ? (
                            <div className="text-muted-foreground py-4">
                                You haven't sent any invitations yet. Visit a lobby and invite users to join your team.
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {sent.map((item) => (
                                    <div
                                        key={item.invitation.id}
                                        className="flex items-center justify-between p-3 border rounded-lg"
                                    >
                                        <div>
                                            <div className="font-semibold">
                                                {item.user?.name} for {item.lobby?.title}
                                            </div>
                                            <div className="text-sm text-muted-foreground">
                                                Status: <Badge variant="outline">{item.invitation.status}</Badge>
                                            </div>
                                        </div>
                                        {item.lobby && (
                                            <Link href={`/lobbies/${item.lobby.id}`}>
                                                <Button variant="outline" size="sm">
                                                    Manage Lobby
                                                </Button>
                                            </Link>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Info Card */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">About Invitations</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 text-sm text-muted-foreground">
                        <p>
                            <span className="font-semibold">Receiving invitations:</span> Team leaders can send you direct invitations to join their lobbies.
                        </p>
                        <p>
                            <span className="font-semibold">Sending invitations:</span> As a team leader, visit your lobby and use the invite form to send invitations to specific users.
                        </p>
                        <p className="pt-2">
                            <Link href="/lobbies" className="text-blue-600 hover:underline">
                                Go to Lobbies →
                            </Link>
                        </p>
                    </CardContent>
                </Card>
            </div>
        </>
    );
}

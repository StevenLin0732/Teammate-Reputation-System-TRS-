'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getCurrentUser, getLobby, getUser } from '@/lib/api';
import type { JoinRequest } from '@/lib/api';
import type { User, Lobby } from '@/lib/types';

interface JoinRequestWithDetails {
    request: JoinRequest;
    lobby?: Lobby;
    requester?: User;
}

export default function JoinRequestsPage() {
    const router = useRouter();
    const [currentUser, setCurrentUser] = useState<User | null>(null);
    const [made, setMade] = useState<JoinRequestWithDetails[]>([]);
    const [received, setReceived] = useState<JoinRequestWithDetails[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function loadData() {
            try {
                const user = await getCurrentUser();
                if (!user) {
                    router.push('/login?next=/join-requests');
                    return;
                }

                setCurrentUser(user);

                // This is a placeholder for now - the old UI had a dedicated page
                // In the Next.js app, join requests are handled directly in lobby details
                // For completeness, we'll show a message with navigation to lobbies
                setLoading(false);
            } catch (err) {
                const msg = err instanceof Error ? err.message : 'Failed to load data';
                setError(msg);
                setLoading(false);
            }
        }

        loadData();
    }, [router]);

    if (loading) {
        return <div className="text-center py-12">Loading...</div>;
    }

    if (error) {
        return (
            <Card>
                <CardContent className="pt-6">
                    <div className="text-red-600">Error: {error}</div>
                </CardContent>
            </Card>
        );
    }

    return (
        <>
            <div className="flex items-end justify-between gap-3 mb-4">
                <div>
                    <h1 className="text-2xl font-semibold mb-1">Join Requests</h1>
                    <div className="text-muted-foreground">
                        Manage your join requests and incoming requests from team members.
                    </div>
                </div>
            </div>

            <div className="grid gap-4">
                {/* Requests Made */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Requests You've Made</CardTitle>
                        <CardDescription>Join requests you've sent to lobbies</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {made.length === 0 ? (
                            <div className="text-muted-foreground py-4">
                                You haven't made any join requests yet.
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {made.map((item) => (
                                    <div
                                        key={item.request.id}
                                        className="flex items-center justify-between p-3 border rounded-lg"
                                    >
                                        <div>
                                            <div className="font-semibold">{item.lobby?.title}</div>
                                            <div className="text-sm text-muted-foreground">
                                                Status: <Badge variant="outline">{item.request.status}</Badge>
                                            </div>
                                        </div>
                                        {item.lobby && (
                                            <Link href={`/lobbies/${item.lobby.id}`}>
                                                <Button variant="outline" size="sm">
                                                    View Lobby
                                                </Button>
                                            </Link>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Requests Received */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Requests Received</CardTitle>
                        <CardDescription>Join requests from users wanting to join your lobbies</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {received.length === 0 ? (
                            <div className="text-muted-foreground py-4">
                                No pending join requests. Created lobbies will show requests here.
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {received.map((item) => (
                                    <div
                                        key={item.request.id}
                                        className="flex items-center justify-between p-3 border rounded-lg"
                                    >
                                        <div>
                                            <div className="font-semibold">{item.requester?.name} requesting to join</div>
                                            <div className="text-sm text-muted-foreground">
                                                Lobby: {item.lobby?.title}
                                            </div>
                                        </div>
                                        {item.lobby && (
                                            <Link href={`/lobbies/${item.lobby.id}`}>
                                                <Button variant="outline" size="sm">
                                                    View Lobby
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
                        <CardTitle className="text-lg">How Join Requests Work</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 text-sm text-muted-foreground">
                        <p>
                            <span className="font-semibold">To request to join a lobby:</span> Navigate to a lobby detail page and click "Request to join".
                        </p>
                        <p>
                            <span className="font-semibold">To manage requests:</span> As a lobby leader, view your lobby detail page to accept or reject join requests.
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

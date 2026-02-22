import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function HomePage() {
  return (
    <>
      <div className="p-4 md:p-8 mb-6 bg-white border rounded-lg shadow-sm">
        <div className="max-w-4xl">
          <h1 className="text-3xl md:text-4xl font-semibold mb-2">
            Teammate Reputation System (TRS)
          </h1>
          <p className="text-lg text-muted-foreground">
            Welcome to TRS, the one-stop solution for serious competitors looking for reputable team-ups.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Users</CardTitle>
            <CardDescription>See seeded users and their basic info.</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/users">
              <Button variant="outline" size="sm">
                Go to users
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Lobbies</CardTitle>
            <CardDescription>Discover teams recruiting for contests and projects.</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/lobbies">
              <Button variant="outline" size="sm">
                Go to lobbies
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

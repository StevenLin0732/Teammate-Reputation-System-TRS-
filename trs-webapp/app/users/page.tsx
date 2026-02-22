import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getUsers, getUserReputation } from '@/lib/api';
import { User, Reputation } from '@/lib/types';

export const dynamic = 'force-dynamic';

async function getUsersWithReputation(): Promise<(User & { reputation: Reputation })[]> {
  const users = await getUsers();
  const usersWithRep = await Promise.all(
    users.map(async (user) => {
      try {
        const rep = await getUserReputation(user.id);
        return { ...user, reputation: rep };
      } catch {
        return { ...user, reputation: { contribution_avg: 0, communication_avg: 0, would_work_again_ratio: null, rating_count: 0 } };
      }
    })
  );
  return usersWithRep;
}

export default async function UsersPage() {
  const users = await getUsersWithReputation();

  return (
    <>
      <div className="flex items-end justify-between gap-3 mb-4">
        <div>
          <h1 className="text-2xl font-semibold mb-1">Users</h1>
          <div className="text-muted-foreground">Seeded users in the demo database.</div>
        </div>
        <Badge variant="secondary">{users.length} total</Badge>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 w-20">ID</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Name</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Major</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Year</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Reputation</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Contact</th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-700 w-40"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {users.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                      No users found. Run the seed script to populate the DB.
                    </td>
                  </tr>
                ) : (
                  users.map((user) => {
                    const rep = user.reputation;
                    return (
                      <tr key={user.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-muted-foreground">{user.id}</td>
                        <td className="px-4 py-3 font-semibold">{user.name}</td>
                        <td className="px-4 py-3">{user.major || '—'}</td>
                        <td className="px-4 py-3">{user.year || '—'}</td>
                        <td className="px-4 py-3">
                          <div className="text-sm">
                            <span className="text-muted-foreground">Contrib</span>{' '}
                            <span className="font-semibold">{rep.contribution_avg}</span>
                            {' · '}
                            <span className="text-muted-foreground">Comm</span>{' '}
                            <span className="font-semibold">{rep.communication_avg}</span>
                            {' · '}
                            <span className="text-muted-foreground">WWA</span>{' '}
                            <span className="font-semibold">
                              {rep.would_work_again_ratio !== null
                                ? `${Math.round(rep.would_work_again_ratio * 100)}%`
                                : '—'}
                            </span>
                            <span className="text-muted-foreground">
                              {' '}(n={rep.rating_count})
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {user.email || user.phone || user.contact || '—'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Link href={`/users/${user.id}`}>
                            <Button variant="outline" size="sm">
                              View profile
                            </Button>
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </>
  );
}

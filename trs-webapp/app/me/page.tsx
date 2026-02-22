import { redirect } from 'next/navigation';
import { getCurrentUser } from '@/lib/api';

export const dynamic = 'force-dynamic';

export default async function MePage() {
  const user = await getCurrentUser();
  if (!user) {
    redirect('/login?next=/me');
  }
  redirect(`/users/${user.id}`);
}

import { redirect } from 'next/navigation';
import { headers, cookies } from 'next/headers';

export const dynamic = 'force-dynamic';

export default async function MePage() {
  // Server-side fetch forwarding the browser's cookie so the Flask API
  // can recognize the session during SSR.
  // Build the Cookie header in a few fallback-friendly ways to support
  // different runtimes (Turbopack vs default). Prefer `headers().get()`
  // when available, otherwise try the `cookies()` store or common cookie
  // names used by Flask.
  const hdrs = headers();
  let cookieHeader = '';

  if (hdrs && typeof (hdrs as any).get === 'function') {
    cookieHeader = (hdrs as any).get('cookie') || '';
  } else {
    try {
      const cookieStore = cookies();
      if (cookieStore && typeof (cookieStore as any).getAll === 'function') {
        const all = (cookieStore as any).getAll();
        cookieHeader = all && all.length ? all.map((c: any) => `${c.name}=${c.value}`).join('; ') : '';
      } else if (cookieStore && typeof (cookieStore as any).get === 'function') {
        // try common Flask cookie names
        const sessionVal = (cookieStore as any).get('session')?.value || (cookieStore as any).get('flask_session')?.value || (cookieStore as any).get('sessionid')?.value;
        if (sessionVal) cookieHeader = `session=${sessionVal}`;
      } else if (hdrs && typeof hdrs === 'object') {
        // last resort: look for a plain 'cookie' property
        cookieHeader = (hdrs as any)['cookie'] || '';
      }
    } catch (e) {
      cookieHeader = '';
    }
  }
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:5000';

  try {
    const res = await fetch(`${API_BASE}/me`, {
      headers: cookieHeader ? { cookie: cookieHeader } : undefined,
      // don't follow redirects automatically so we can inspect them
      redirect: 'manual',
    });

    if (res.ok) {
      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const user = await res.json();
        redirect(`/users/${user.id}`);
      }
      // If server returned HTML (profile page), we can attempt to parse
      // the final location from a redirect header below.
    }

    if (res.status === 302) {
      const location = res.headers.get('location');
      if (location && location.includes('/users/')) {
        // redirect to the backend-provided user URL
        redirect(location);
      }
    }
  } catch (e) {
    // fallthrough to redirect to login
  }

  redirect('/login?next=/me');
}

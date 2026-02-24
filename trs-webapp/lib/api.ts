import { User, Lobby, Reputation, Submission, Rating } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:5000';

async function fetchWithCredentials(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers = new Headers(options.headers);
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  
  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers,
  });
  return response;
}

export async function login(email: string, password: string): Promise<void> {
  const formData = new FormData();
  formData.append('email', email);
  formData.append('password', password);

  const response = await fetchWithCredentials(`${API_BASE}/login`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    let msg = 'Login failed';
    try {
      const data = await response.json();
      if (data && data.error) msg = data.error;
    } catch {
      try {
        const text = await response.text();
        if (text) msg = text;
      } catch {}
    }
    throw new Error(msg);
  }
}

export async function register(data: {
  name: string;
  email: string;
  password: string;
  major?: string;
  year?: string;
  bio?: string;
  contact?: string;
  phone?: string;
}): Promise<void> {
  const formData = new FormData();
  Object.entries(data).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      formData.append(key, value);
    }
  });

  const response = await fetch(`${API_BASE}/register`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Registration failed');
  }
}

export async function logout(): Promise<void> {
  await fetchWithCredentials(`${API_BASE}/logout`, {
    method: 'POST',
  });
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    const response = await fetchWithCredentials(`${API_BASE}/me`, {
      redirect: 'manual',
    });
    // If server returns JSON user object (common), return it
    const contentType = response.headers.get('content-type') || '';
    if (response.ok && contentType.includes('application/json')) {
      return response.json();
    }

    // Some servers redirect /me to /users/<id> via 302; follow that
    if (response.status === 302) {
      const location = response.headers.get('location');
      if (location && location.includes('/users/')) {
        const userId = parseInt(location.split('/users/')[1]);
        if (userId) {
          return getUser(userId);
        }
      }
    }

    return null;
  } catch {
    return null;
  }
}

export async function getLobbies(): Promise<Lobby[]> {
  const response = await fetchWithCredentials(`${API_BASE}/api/lobbies`);
  if (!response.ok) {
    throw new Error('Failed to fetch lobbies');
  }
  return response.json();
}

export async function getLobby(lobbyId: number): Promise<Lobby> {
  const response = await fetchWithCredentials(`${API_BASE}/api/lobbies/${lobbyId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch lobby');
  }
  return response.json();
}

export async function getUsers(): Promise<User[]> {
  const response = await fetchWithCredentials(`${API_BASE}/api/users`);
  if (!response.ok) {
    throw new Error('Failed to fetch users');
  }
  return response.json();
}

export async function getUser(userId: number): Promise<User> {
  const response = await fetchWithCredentials(`${API_BASE}/api/users/${userId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch user');
  }
  return response.json();
}

export async function updateUserProfile(
  userId: number,
  field: string,
  value: string
): Promise<void> {
  const formData = new FormData();
  formData.append('field', field);
  formData.append('value', value);

  const response = await fetchWithCredentials(`${API_BASE}/users/${userId}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Failed to update profile');
  }
}


export async function createLobby(data: {
  title: string;
  contest_link?: string;
  leader_id?: number;
}): Promise<Lobby> {
  const response = await fetchWithCredentials(`${API_BASE}/api/lobbies`, {
    method: 'POST',
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error('Failed to create lobby');
  }
  return response.json();
}

export async function joinLobby(lobbyId: number, userId: number): Promise<void> {
  const response = await fetchWithCredentials(
    `${API_BASE}/api/lobbies/${lobbyId}/join`,
    {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to join lobby');
  }
}

export async function submitProof(
  teamId: number,
  proof: string,
  submitterId: number
): Promise<Submission> {
  const response = await fetchWithCredentials(
    `${API_BASE}/api/teams/${teamId}/submit`,
    {
      method: 'POST',
      body: JSON.stringify({ proof, submitter_id: submitterId }),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to submit proof');
  }
  return response.json();
}

export async function rateMember(
  teamId: number,
  data: {
    rater_id: number;
    target_user_id: number;
    contribution: number;
    communication: number;
    would_work_again: boolean;
    comment?: string;
  }
): Promise<Rating> {
  const response = await fetchWithCredentials(
    `${API_BASE}/api/teams/${teamId}/ratings`,
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to submit rating');
  }
  return response.json();
}

export async function deleteRating(
  lobbyId: number,
  ratingId: number
): Promise<void> {
  const response = await fetchWithCredentials(
    `${API_BASE}/lobbies/${lobbyId}/ratings/${ratingId}/delete`,
    {
      method: 'POST',
    }
  );

  if (!response.ok) {
    throw new Error('Failed to delete rating');
  }
}

export async function deleteProof(
  lobbyId: number,
  submissionId: number
): Promise<void> {
  const response = await fetchWithCredentials(
    `${API_BASE}/lobbies/${lobbyId}/submissions/${submissionId}/delete`,
    {
      method: 'POST',
    }
  );

  if (!response.ok) {
    throw new Error('Failed to delete proof');
  }
}

export async function inviteToLobby(
  lobbyId: number,
  targetEmail: string
): Promise<void> {
  const formData = new FormData();
  formData.append('target_email', targetEmail);

  const response = await fetchWithCredentials(
    `${API_BASE}/lobbies/${lobbyId}/invite`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    throw new Error('Failed to send invitation');
  }
}

export async function getUserReputation(userId: number): Promise<Reputation> {
  const response = await fetchWithCredentials(
    `${API_BASE}/api/users/${userId}/reputation`
  );
  if (!response.ok) {
    throw new Error('Failed to fetch reputation');
  }
  return response.json();
}

export async function updateLobby(
  lobbyId: number,
  data: { title: string; contest_link?: string }
): Promise<void> {
  const formData = new FormData();
  formData.append('action', 'save');
  formData.append('title', data.title);
  if (data.contest_link) {
    formData.append('contest_link', data.contest_link);
  }

  const response = await fetchWithCredentials(`${API_BASE}/lobbies/${lobbyId}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Failed to update lobby');
  }
}

export async function lockTeam(lobbyId: number): Promise<void> {
  const formData = new FormData();
  formData.append('action', 'lock_team');

  const response = await fetchWithCredentials(`${API_BASE}/lobbies/${lobbyId}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Failed to lock team');
  }
}

export async function finishContest(lobbyId: number): Promise<void> {
  const formData = new FormData();
  formData.append('action', 'finish_contest');

  const response = await fetchWithCredentials(`${API_BASE}/lobbies/${lobbyId}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Failed to finish contest');
  }
}

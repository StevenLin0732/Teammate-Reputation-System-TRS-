import { User, Lobby, Reputation, Submission, Rating } from "./types";

// const API_BASE = typeof window === "undefined" ? "http://127.0.0.1:5000" : "";
const API_BASE = "http://localhost:5000";

export async function updateUserProfile(
	userId: number,
	data: {
		name?: string;
		major?: string;
		year?: string;
		bio?: string;
		contact?: string;
		phone?: string;
	},
): Promise<User> {
	return fetchWithCredentials<User>(`${API_BASE}/api/users/${userId}`, {
		method: "PATCH",
		body: JSON.stringify(data),
	});
}

async function fetchWithCredentials<T = any>(
	url: string,
	options: RequestInit = {},
): Promise<T> {
	const headers = new Headers(options.headers);

	if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
		headers.set("Content-Type", "application/json");
	}

	const response = await fetch(url, {
		...options,
		credentials: "include",
		headers,
	});

	if (!response.ok) {
		let message = `Request failed with status ${response.status}`;
		try {
			const data = await response.json();
			if (data?.error) message = data.error;
		} catch {
			// ignore JSON parse errors
		}
		throw new Error(message);
	}
	if (response.status === 204) {
		return undefined as T;
	}

	return (await response.json()) as T;
}

// Auth

export async function login(
	email: string,
	password: string,
): Promise<{ user: User }> {
	return fetchWithCredentials<{ user: User }>(`${API_BASE}/api/auth/login`, {
		method: "POST",
		body: JSON.stringify({ email, password }),
	});
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
}): Promise<{ user: User }> {
	return fetchWithCredentials<{ user: User }>(`${API_BASE}/api/auth/register`, {
		method: "POST",
		body: JSON.stringify(data),
	});
}

export async function logout(): Promise<void> {
	await fetchWithCredentials(`${API_BASE}/api/auth/logout`, {
		method: "POST",
	});
}

export async function getCurrentUser(): Promise<User | null> {
	const res = await fetchWithCredentials<{ user: User | null }>(
		`${API_BASE}/api/auth/me`,
	);
	return res.user;
}

// Users

export async function getUsers(): Promise<User[]> {
	return fetchWithCredentials<User[]>(`${API_BASE}/api/users`);
}

export async function getUser(
	userId: number,
): Promise<User & { lobbies: Lobby[] }> {
	return fetchWithCredentials<User & { lobbies: Lobby[] }>(
		`${API_BASE}/api/users/${userId}`,
	);
}

export async function createUser(data: {
	name?: string;
	email: string;
	password: string;
	major?: string;
	year?: string;
	lobby_id?: number;
}): Promise<User> {
	return fetchWithCredentials<User>(`${API_BASE}/api/users`, {
		method: "POST",
		body: JSON.stringify(data),
	});
}

export async function getUserReputation(userId: number): Promise<Reputation> {
	return fetchWithCredentials<Reputation>(
		`${API_BASE}/api/users/${userId}/reputation`,
	);
}

// Lobbies

export async function getLobbies(): Promise<Lobby[]> {
	return fetchWithCredentials<Lobby[]>(`${API_BASE}/api/lobbies`);
}

export async function getLobby(
	lobbyId: number,
): Promise<Lobby & { participants: User[] }> {
	return fetchWithCredentials<Lobby & { participants: User[] }>(
		`${API_BASE}/api/lobbies/${lobbyId}`,
	);
}

export async function createLobby(data: {
	title: string;
	contest_link?: string;
}): Promise<Lobby> {
	return fetchWithCredentials<Lobby>(`${API_BASE}/api/lobbies`, {
		method: "POST",
		body: JSON.stringify(data),
	});
}

export async function joinLobby(lobbyId: number): Promise<any> {
	// backend uses session-based current user; body not required
	return fetchWithCredentials(`${API_BASE}/api/lobbies/${lobbyId}/join`, {
		method: "POST",
	});
}

export async function finishContest(lobbyId: number): Promise<Lobby> {
	return fetchWithCredentials<Lobby>(
		`${API_BASE}/api/lobbies/${lobbyId}/finish`,
		{
			method: "POST",
		},
	);
}

// Teams, submissions, ratings

export async function lockTeam(teamId: number): Promise<any> {
	return fetchWithCredentials(`${API_BASE}/api/teams/${teamId}/lock`, {
		method: "POST",
	});
}

export async function submitProof(
	teamId: number,
	proof: string,
	submitterId?: number,
): Promise<Submission> {
	return fetchWithCredentials<Submission>(
		`${API_BASE}/api/teams/${teamId}/submit`,
		{
			method: "POST",
			body: JSON.stringify({ proof, submitter_id: submitterId }),
		},
	);
}

export async function rateMember(
	teamId: number,
	data: {
		rater_id?: number;
		target_user_id: number;
		contribution: number;
		communication: number;
		would_work_again: boolean;
		comment?: string;
	},
): Promise<Rating> {
	return fetchWithCredentials<Rating>(
		`${API_BASE}/api/teams/${teamId}/ratings`,
		{
			method: "POST",
			body: JSON.stringify(data),
		},
	);
}

// Join requests

export async function createJoinRequest(lobbyId: number): Promise<any> {
	return fetchWithCredentials(
		`${API_BASE}/api/lobbies/${lobbyId}/join-requests`,
		{
			method: "POST",
		},
	);
}

export async function listJoinRequests(
	lobbyId: number,
	status: "pending" | "accepted" | "rejected" | "canceled" = "pending",
): Promise<any[]> {
	const params = new URLSearchParams({ status });
	return fetchWithCredentials<any[]>(
		`${API_BASE}/api/lobbies/${lobbyId}/join-requests?${params.toString()}`,
	);
}

export async function decideJoinRequest(
	lobbyId: number,
	requestId: number,
	decision: "accept" | "reject",
): Promise<any> {
	return fetchWithCredentials(
		`${API_BASE}/api/lobbies/${lobbyId}/join-requests/${requestId}/decision`,
		{
			method: "POST",
			body: JSON.stringify({ decision }),
		},
	);
}

// Invitations

export async function inviteToLobby(
	lobbyId: number,
	targetEmail: string,
): Promise<any> {
	return fetchWithCredentials(`${API_BASE}/api/lobbies/${lobbyId}/invite`, {
		method: "POST",
		body: JSON.stringify({ target_email: targetEmail }),
	});
}

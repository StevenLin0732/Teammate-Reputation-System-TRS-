export interface User {
  id: number;
  name: string;
  major?: string;
  year?: string;
  bio?: string;
  contact?: string;
  phone?: string;
  email?: string;
}

export interface Reputation {
  contribution_avg: number;
  communication_avg: number;
  would_work_again_ratio: number | null;
  rating_count: number;
}

export interface Lobby {
  id: number;
  title: string;
  contest_link?: string;
  leader_id?: number;
  finished: boolean;
  finished_at?: string;
  participant_count?: number;
  participants?: User[];
  team_locked?: boolean;
  role?: string;
}

export interface Team {
  id: number;
  lobby_id: number;
  locked: boolean;
  members: number[];
  submissions: Submission[];
}

export interface Submission {
  id: number;
  team_id: number;
  submitter_id?: number;
  proof_link: string;
  created_at?: string;
}

export interface Rating {
  id: number;
  team_id: number;
  rater_id: number;
  target_user_id: number;
  contribution: number;
  communication: number;
  would_work_again: boolean;
  comment?: string;
}

export interface Invitation {
  id: number;
  lobby_id: number;
  team_id: number;
  applicant_id: number;
  target_user_id: number;
  token: string;
  status: string;
  created_at?: string;
  responded_at?: string;
}

export interface FlashMessage {
  category: 'success' | 'danger' | 'warning' | 'info' | 'secondary';
  message: string;
}

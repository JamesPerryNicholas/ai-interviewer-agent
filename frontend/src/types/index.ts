export interface AuthUser {
  id: number;
  username: string;
  display_name: string | null;
  career_status: string;
  email: string;
  avatar_url: string | null;
  created_at: string;
}

export interface LoginRecord {
  id: number;
  login_at: string;
  ip_address: string | null;
  user_agent: string | null;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface ResumeResponse {
  id: number;
  original_filename: string;
  file_url: string;
  content: string;
  created_at: string;
  extracted_info: ResumeAnalysis | null;
}

export interface ResumeAnalysis {
  skills: string[];
  projects: string[];
  experience: string;
  level: string;
  suggestions: string[];
}

export interface JobPositionPayload {
  company: string;
  position: string;
  description: string;
}

export interface JobPosition extends JobPositionPayload {
  id: number;
  created_at: string;
}

export interface GeneratedQuestion {
  id: number;
  job_id: number;
  category: string;
  difficulty: string;
  question: string;
  answer: string | null;
  created_at: string;
}

export interface InterviewSession {
  id: number;
  user_id: number;
  resume_id: number;
  job_id: number;
  position?: string | null;
  status: "in_progress" | "completed" | "cancelled" | string;
  completed_questions: number;
  total_questions: number;
  start_time: string;
  end_time: string | null;
}

export interface InterviewMessage {
  id: number;
  interview_id: number;
  role: "user" | "assistant";
  content: string;
  token_count: number | null;
  created_at: string;
}

export interface InterviewStartResponse {
  interview: InterviewSession;
  first_message: InterviewMessage;
}

export interface InterviewHistoryResponse {
  interview: InterviewSession;
  messages: InterviewMessage[];
}

export interface InterviewListItem {
  id: number;
  position: string | null;
  status: string;
  start_time: string;
  end_time: string | null;
  report_id: number | null;
  total_score: number | null;
}

export interface EvaluationReport {
  id: number;
  interview_id: number;
  total_score: number;
  technical_score: number;
  communication_score: number;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  created_at: string;
  answers: AnswerEvaluation[];
}

export interface AnswerEvaluation {
  id: number;
  question_id: number | null;
  question: string | null;
  answer: string;
  score: number | null;
  analysis: string | null;
  created_at: string;
}

export interface InterviewFinishResponse {
  interview: InterviewSession;
  report: EvaluationReport;
}

export interface InterviewRecord {
  id: number;
  title: string;
  date: string;
  score: number;
  status: "completed" | "in-progress";
}

export interface ChatMessage {
  id: number | string;
  role: "ai" | "user";
  content: string;
  time: string;
}

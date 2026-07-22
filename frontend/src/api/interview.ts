import request, { TOKEN_KEY } from "./request";
import type {
  InterviewFinishResponse,
  InterviewHistoryResponse,
  InterviewListItem,
  InterviewStartResponse,
} from "../types";

const API_BASE_URL = "http://localhost:8000";

export async function startInterview(resumeId: number, jobId: number): Promise<InterviewStartResponse> {
  // Starting a session generates a fresh set of eight questions through the
  // LLM, so it must not use the shared 10-second request timeout.
  const response = await request.post<InterviewStartResponse>(
    "/api/interview/start",
    {
      resume_id: resumeId,
      job_id: jobId,
    },
    { timeout: 180_000 },
  );
  return response.data;
}

export async function getInterviewHistory(interviewId: number): Promise<InterviewHistoryResponse> {
  const response = await request.get<InterviewHistoryResponse>(`/api/interview/history/${interviewId}`);
  return response.data;
}

export async function listInterviews(): Promise<InterviewListItem[]> {
  const response = await request.get<InterviewListItem[]>("/api/interview/list");
  return response.data;
}

export async function finishInterview(interviewId: number): Promise<InterviewFinishResponse> {
  // Report generation includes a non-streaming DeepSeek request and may take
  // longer than the normal 10-second API timeout.
  const response = await request.post<InterviewFinishResponse>(
    `/api/interview/${interviewId}/finish`,
    undefined,
    { timeout: 180_000 },
  );
  return response.data;
}

/** End a session explicitly and generate a partial report from saved answers. */
export async function endInterviewEarly(interviewId: number): Promise<InterviewFinishResponse> {
  const response = await request.post<InterviewFinishResponse>(
    `/api/interview/${interviewId}/end`,
    undefined,
    { timeout: 180_000 },
  );
  return response.data;
}

export async function recallInterviewMessage(
  interviewId: number,
  messageId: number,
): Promise<InterviewHistoryResponse> {
  const response = await request.delete<InterviewHistoryResponse>(
    `/api/interview/${interviewId}/messages/${messageId}`,
  );
  return response.data;
}

export async function streamInterview(
  interviewId: number,
  message: string,
  onToken: (content: string) => void,
): Promise<void> {
  const token = localStorage.getItem(TOKEN_KEY);
  const response = await fetch(`${API_BASE_URL}/api/interview/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ interview_id: interviewId, message }),
  });

  if (!response.ok) {
    let detail = "无法继续面试，请稍后重试";
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail || detail;
    } catch {
      // Keep the generic message when the backend does not return JSON.
    }
    throw new Error(detail);
  }

  if (!response.body) throw new Error("当前浏览器不支持流式输出");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let streamFinished = false;

  const processEvent = (event: string) => {
    const line = event.split(/\r?\n/).find((item) => item.startsWith("data:"));
    if (!line) return;
    const data = line.slice(5).trim();
    if (data === "[DONE]") {
      streamFinished = true;
      return;
    }
    const payload = JSON.parse(data) as { content?: string; error?: string };
    if (payload.error) throw new Error(payload.error);
    if (payload.content) onToken(payload.content);
  };

  while (!streamFinished) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const events = buffer.split(/\r?\n\r?\n/);
    buffer = events.pop() || "";

    for (const event of events) {
      processEvent(event);
      if (streamFinished) break;
    }

    if (done) {
      if (buffer.trim() && !streamFinished) processEvent(buffer);
      break;
    }
  }
}

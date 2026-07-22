import request from "./request";
import type { GeneratedQuestion, JobPosition, JobPositionPayload } from "../types";

export async function createJob(payload: JobPositionPayload): Promise<JobPosition> {
  const response = await request.post<JobPosition>("/api/job/create", payload);
  return response.data;
}

export async function listJobs(): Promise<JobPosition[]> {
  const response = await request.get<JobPosition[]>("/api/job/list");
  return response.data;
}

export async function deleteJob(jobId: number): Promise<void> {
  await request.delete(`/api/job/${jobId}`);
}

export async function generateQuestions(
  resumeId: number,
  jobId: number,
): Promise<GeneratedQuestion[]> {
  const response = await request.post<GeneratedQuestion[]>("/api/interview/generate", {
    resume_id: resumeId,
    job_id: jobId,
  }, {
    timeout: 120_000,
  });
  return response.data;
}

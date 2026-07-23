import request from "./request";
import type { ResumeAnalysis, ResumeResponse } from "../types";

export async function uploadResume(
  file: File,
  onProgress?: (percentage: number) => void,
): Promise<ResumeResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await request.post<ResumeResponse>("/api/resume/upload", formData, {
    onUploadProgress: (event) => {
      if (event.total) {
        onProgress?.(Math.round((event.loaded / event.total) * 100));
      }
    },
  });

  return response.data;
}

export async function getLatestResume(): Promise<ResumeResponse> {
  const response = await request.get<ResumeResponse>("/api/resume/latest");
  return response.data;
}

export async function analyzeResume(resumeId: number): Promise<ResumeAnalysis> {
  // Resume analysis calls the LLM and can take longer than ordinary API calls.
  const response = await request.post<ResumeAnalysis>(`/api/resume/${resumeId}/analyze`, undefined, {
    timeout: 120_000,
  });
  return response.data;
}

export async function downloadResume(resumeId: number, filename: string): Promise<void> {
  const response = await request.get<Blob>(`/api/resume/${resumeId}/download`, {
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

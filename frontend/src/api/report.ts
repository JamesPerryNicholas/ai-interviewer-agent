import request from "./request";
import type { EvaluationReport } from "../types";

export async function getReport(interviewId: number): Promise<EvaluationReport> {
  const response = await request.get<EvaluationReport>(`/api/report/${interviewId}`);
  return response.data;
}

export async function downloadReportPdf(interviewId: number): Promise<void> {
  const response = await request.get<Blob>(`/api/report/${interviewId}/pdf`, {
    responseType: "blob",
  });
  const contentDisposition = response.headers["content-disposition"] as string | undefined;
  const encodedName = contentDisposition?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const filename = encodedName
    ? decodeURIComponent(encodedName)
    : "面试评估报告.pdf";
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

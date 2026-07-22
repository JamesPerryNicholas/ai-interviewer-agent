"""Service for evaluating an interview and persisting its report."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.llm.deepseek import DeepSeekClient
from app.models.answer import Answer
from app.models.evaluation_report import EvaluationReport
from app.models.interview import Interview
from app.models.job_position import JobPosition
from app.models.message import Message
from app.models.question import Question
from app.models.resume import Resume
from app.prompts.evaluation_prompt import build_fast_evaluation_messages
from app.schemas.evaluation import (
    AnswerEvaluationResponse,
    EvaluationPayload,
    EvaluationReportResponse,
)
from app.services.llm_usage_service import add_llm_usage


logger = logging.getLogger(__name__)


class EvaluationError(RuntimeError):
    """Base error for report generation."""


class EvaluationResourceNotFoundError(EvaluationError):
    """Raised when an interview is missing or not owned by the user."""


class EvaluationNotReadyError(EvaluationError):
    """Raised when an interview has no candidate answers."""


class EvaluationService:
    """Coordinate report generation and evaluation persistence."""

    def __init__(self, session: AsyncSession, deepseek_client: DeepSeekClient | None = None) -> None:
        self.session = session
        self.deepseek_client = deepseek_client or DeepSeekClient()

    async def evaluate_interview(
        self, *, user_id: int, interview_id: int, allow_partial: bool = False
    ) -> EvaluationReportResponse:
        """Evaluate an owned interview, save answer audit rows, and close it."""

        interview = await self._load_interview(user_id=user_id, interview_id=interview_id)
        existing_report = await self.session.scalar(
            select(EvaluationReport).where(EvaluationReport.interview_id == interview_id)
        )
        # A browser timeout must not cause a second DeepSeek evaluation when
        # the backend completed the original request in the background.
        if existing_report is not None and interview.status in {"completed", "ended_early"}:
            return await self._build_report_response(existing_report)

        messages = list(
            (
                await self.session.execute(
                    select(Message)
                    .where(Message.interview_id == interview_id)
                    .order_by(Message.created_at.asc(), Message.id.asc())
                )
            ).scalars().all()
        )
        # Invalid answers remain visible in the transcript for transparency,
        # but must not count toward completion or answer scoring.
        candidate_messages = [
            message
            for message in messages
            if message.role == "user" and message.is_valid_answer is not False
        ]
        if not candidate_messages:
            raise EvaluationNotReadyError("请先完成至少一轮回答，再生成面试报告")

        resume = await self.session.scalar(select(Resume).where(Resume.id == interview.resume_id))
        job = await self.session.scalar(select(JobPosition).where(JobPosition.id == interview.job_id))
        questions = list(
            (
                await self.session.execute(
                    select(Question).where(Question.job_id == interview.job_id).order_by(Question.id.asc())
                )
            ).scalars().all()
        )
        if resume is None or job is None:
            raise EvaluationResourceNotFoundError("简历或岗位不存在")
        expected_answers = interview.total_questions or len(questions)
        if expected_answers and len(candidate_messages) < expected_answers and not allow_partial:
            raise EvaluationNotReadyError(
                f"请先完成全部面试问题，还需要回答{expected_answers - len(candidate_messages)}题"
            )

        evaluation_messages = [
            message
            for message in messages
            if message.role == "assistant" or message.is_valid_answer is not False
        ]

        result = await self.deepseek_client.chat_completion(
            messages=build_fast_evaluation_messages(
                resume_analysis=resume.extracted_info,
                job_description=job.description,
                messages=[
                    {"role": message.role, "content": message.content}
                    for message in evaluation_messages
                ],
            ),
            model=settings.deepseek_model,
            json_mode=False,
            allow_reasoning_json_fallback=True,
            max_tokens=settings.deepseek_evaluation_max_tokens,
            temperature=0.2,
        )
        add_llm_usage(
            self.session,
            client=self.deepseek_client,
            user_id=user_id,
            feature="interview_evaluation",
        )
        payload = self._parse_payload(result)

        await self.session.execute(delete(Answer).where(Answer.interview_id == interview_id))
        hidden_evaluations = payload.answer_evaluations
        question_snapshot = interview.question_snapshot or []
        for index, message in enumerate(candidate_messages):
            snapshot_item = question_snapshot[index] if index < len(question_snapshot) else {}
            question_id = (
                snapshot_item.get("id")
                if isinstance(snapshot_item, dict) and isinstance(snapshot_item.get("id"), int)
                else None
            )
            if not question_snapshot and questions:
                question_id = questions[min(index, len(questions) - 1)].id
            evaluation = hidden_evaluations[index] if index < len(hidden_evaluations) else None
            self.session.add(
                Answer(
                    interview_id=interview_id,
                    question_id=question_id,
                    answer=message.content,
                    score=evaluation.score if evaluation else None,
                    analysis=evaluation.analysis if evaluation else None,
                )
            )

        report = await self.session.scalar(
            select(EvaluationReport).where(EvaluationReport.interview_id == interview_id)
        )
        report_data = payload.model_dump(exclude={"answer_evaluations"})
        if report is None:
            report = EvaluationReport(interview_id=interview_id, **report_data)
            self.session.add(report)
        else:
            for key, value in report_data.items():
                setattr(report, key, value)

        # Preserve the explicit early-end marker so history and dashboard can
        # accurately distinguish a completed interview from a partial one.
        if interview.status != "ended_early":
            interview.status = "completed"
        interview.end_time = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(report)
        return await self._build_report_response(report)

    async def get_report(self, *, user_id: int, interview_id: int) -> EvaluationReportResponse:
        """Return a report only when it belongs to the authenticated user."""

        await self._load_interview(user_id=user_id, interview_id=interview_id)
        report = await self.session.scalar(
            select(EvaluationReport).where(EvaluationReport.interview_id == interview_id)
        )
        if report is None:
            raise EvaluationResourceNotFoundError("面试报告不存在")
        return await self._build_report_response(report)

    async def get_report_context(self, *, user_id: int, interview_id: int):
        """Return the owned interview context needed for PDF rendering."""

        interview = await self._load_interview(user_id=user_id, interview_id=interview_id)
        job = await self.session.scalar(select(JobPosition).where(JobPosition.id == interview.job_id))
        if job is None:
            raise EvaluationResourceNotFoundError("岗位不存在")
        return interview, job, await self.get_report(user_id=user_id, interview_id=interview_id)

    async def _build_report_response(self, report: EvaluationReport) -> EvaluationReportResponse:
        interview = await self.session.scalar(
            select(Interview).where(Interview.id == report.interview_id)
        )
        question_snapshot = interview.question_snapshot if interview else []
        rows = list(
            (
                await self.session.execute(
                    select(Answer, Question.question)
                    .outerjoin(Question, Question.id == Answer.question_id)
                    .where(Answer.interview_id == report.interview_id)
                    .order_by(Answer.created_at.asc(), Answer.id.asc())
                )
            ).all()
        )
        return EvaluationReportResponse(
            total_score=report.total_score,
            technical_score=report.technical_score,
            communication_score=report.communication_score,
            strengths=report.strengths,
            weaknesses=report.weaknesses,
            suggestions=report.suggestions,
            id=report.id,
            interview_id=report.interview_id,
            created_at=report.created_at,
            answers=[
                AnswerEvaluationResponse(
                    id=answer.id,
                    question_id=answer.question_id,
                    question=(
                        question
                        or (
                            question_snapshot[index].get("question")
                            if index < len(question_snapshot)
                            and isinstance(question_snapshot[index], dict)
                            else None
                        )
                    ),
                    answer=answer.answer,
                    score=answer.score,
                    analysis=answer.analysis,
                    created_at=answer.created_at,
                )
                for index, (answer, question) in enumerate(rows)
            ],
        )

    async def _load_interview(self, *, user_id: int, interview_id: int) -> Interview:
        interview = await self.session.scalar(
            select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id)
        )
        if interview is None:
            raise EvaluationResourceNotFoundError("面试不存在")
        return interview

    @staticmethod
    def _parse_payload(raw_content: str) -> EvaluationPayload:
        """Parse fenced or reasoning-wrapped JSON defensively."""

        content = raw_content.strip()
        if "```" in content:
            content = content.replace("```json", "").replace("```", "").strip()
        try:
            data: Any = json.loads(content)
        except json.JSONDecodeError as error:
            start, end = content.find("{"), content.rfind("}")
            if start < 0 or end <= start:
                raise EvaluationError("AI返回的评分结果不是有效JSON") from error
            try:
                data = json.loads(content[start : end + 1])
            except json.JSONDecodeError as nested_error:
                raise EvaluationError("AI返回的评分结果不是有效JSON") from nested_error
        try:
            return EvaluationPayload.model_validate(data)
        except Exception as error:
            logger.exception("Invalid evaluation payload from DeepSeek")
            raise EvaluationError("AI返回的评分字段不完整") from error

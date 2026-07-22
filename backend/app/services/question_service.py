"""Service for generating and persisting personalized interview questions."""

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.llm.deepseek import DeepSeekClient
from app.models.job_position import JobPosition
from app.models.interview import Interview
from app.models.question import Question
from app.models.resume import Resume
from app.models.user import User
from app.prompts.interview_prompt import (
    build_interview_question_messages,
    build_simulation_question_messages,
)
from app.schemas.question import GeneratedQuestion, QuestionResponse
from app.services.llm_usage_service import add_llm_usage


class QuestionGenerationError(RuntimeError):
    """Raised when generated question output cannot be persisted."""


class QuestionResourceNotFoundError(QuestionGenerationError):
    """Raised when the resume or job is missing or not owned by the user."""


class ResumeAnalysisRequiredError(QuestionGenerationError):
    """Raised when questions are requested before resume analysis."""


class QuestionService:
    """Generate questions from an owned resume profile and job description."""

    def __init__(
        self,
        session: AsyncSession,
        deepseek_client: DeepSeekClient | None = None,
    ) -> None:
        self.session = session
        self.deepseek_client = deepseek_client or DeepSeekClient()

    async def generate_questions(
        self,
        resume_id: int,
        job_id: int,
        user_id: int,
    ) -> list[QuestionResponse]:
        """Generate and replace the current question set for one owned job."""

        resume_result = await self.session.execute(
            select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
        )
        resume = resume_result.scalar_one_or_none()

        job_result = await self.session.execute(
            select(JobPosition).where(JobPosition.id == job_id, JobPosition.user_id == user_id)
        )
        job = job_result.scalar_one_or_none()
        if resume is None or job is None:
            raise QuestionResourceNotFoundError("未找到简历或岗位")
        if not resume.extracted_info:
            raise ResumeAnalysisRequiredError("请先完成简历分析，再生成面试题")

        user = await self.session.scalar(select(User).where(User.id == user_id))
        career_status = user.career_status if user and user.career_status else "实习求职"

        messages = build_interview_question_messages(
            resume_analysis=resume.extracted_info,
            career_status=career_status,
            company=job.company,
            position=job.position,
            job_description=job.description,
        )
        generated_questions: list[GeneratedQuestion] | None = None
        last_error: QuestionGenerationError | None = None
        for attempt in range(3):
            if attempt:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "请重新生成且严格返回 8 个对象，只返回JSON数组。"
                            "question字段必须全部使用简体中文，不能出现英文完整句子；"
                            "category和difficulty继续使用规定的英文枚举值。"
                        ),
                    }
                )

            raw_content = await self.deepseek_client.chat_completion(
                messages=messages,
                model=settings.deepseek_model,
                json_mode=False,
                allow_reasoning_json_fallback=True,
            )
            add_llm_usage(
                self.session,
                client=self.deepseek_client,
                user_id=user_id,
                feature="question_generation",
            )
            try:
                candidate = self._parse_questions(raw_content)
            except QuestionGenerationError as error:
                last_error = error
                continue
            generated_questions = candidate
            if len(candidate) == 8 and self._has_chinese_questions(candidate):
                break

        if generated_questions is None or len(generated_questions) != 8:
            raise QuestionGenerationError("AI 未能生成 8 个有效的面试问题，请稍后重试") from last_error

        try:
            await self.session.execute(delete(Question).where(Question.job_id == job_id))
            question_models = [
                Question(
                    job_id=job_id,
                    category=item.category,
                    difficulty=item.difficulty,
                    question=item.question,
                )
                for item in generated_questions
            ]
            self.session.add_all(question_models)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        for question in question_models:
            await self.session.refresh(question)
        return [QuestionResponse.model_validate(question) for question in question_models]

    async def generate_simulation_questions(
        self,
        *,
        resume_id: int,
        job_id: int,
        user_id: int,
    ) -> list[dict[str, str]]:
        """Generate a new, non-repeating question set for one interview.

        These questions are intentionally not persisted to the reference
        ``questions`` table. They are stored in the interview snapshot by the
        caller, so the preparation page and live interview remain separate.
        """

        resume = await self.session.scalar(
            select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
        )
        job = await self.session.scalar(
            select(JobPosition).where(JobPosition.id == job_id, JobPosition.user_id == user_id)
        )
        if resume is None or job is None:
            raise QuestionResourceNotFoundError("未找到简历或岗位")
        if not resume.extracted_info:
            raise ResumeAnalysisRequiredError("请先完成简历分析，再开始模拟面试")

        user = await self.session.scalar(select(User).where(User.id == user_id))
        career_status = user.career_status if user and user.career_status else "实习求职"
        history_result = await self.session.execute(
            select(Interview.question_snapshot)
            .where(
                Interview.user_id == user_id,
                Interview.resume_id == resume_id,
                Interview.job_id == job_id,
            )
            .order_by(Interview.id.desc())
        )
        excluded_questions: list[str] = []
        for snapshot in history_result.scalars().all():
            if not isinstance(snapshot, list):
                continue
            excluded_questions.extend(
                str(item.get("question", "")).strip()
                for item in snapshot
                if isinstance(item, dict) and item.get("question")
            )

        base_messages = build_simulation_question_messages(
            resume_analysis=resume.extracted_info,
            career_status=career_status,
            company=job.company,
            position=job.position,
            job_description=job.description,
            excluded_questions=excluded_questions,
            generation_nonce=datetime.now(timezone.utc).isoformat(),
        )
        last_error: QuestionGenerationError | None = None
        for attempt in range(4):
            messages = [dict(message) for message in base_messages]
            if attempt:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "上一次结果不符合要求。请完全重新设计 8 道问题：每道问题必须是中文，"
                            "本批次内部不能重复，也不能与历史面试问题重复；只返回 JSON 数组。"
                        ),
                    }
                )
            try:
                raw_content = await self.deepseek_client.chat_completion(
                    messages=messages,
                    model=settings.deepseek_model,
                    json_mode=False,
                    allow_reasoning_json_fallback=True,
                    max_tokens=settings.deepseek_question_max_tokens,
                    temperature=0.7,
                )
                add_llm_usage(
                    self.session,
                    client=self.deepseek_client,
                    user_id=user_id,
                    feature="simulation_question_generation",
                )
                generated = self._parse_questions(raw_content)
                if len(generated) != 8:
                    raise QuestionGenerationError("模拟面试必须生成 8 道问题")
                normalized = [self._question_key(item.question) for item in generated]
                excluded_keys = {self._question_key(item) for item in excluded_questions}
                if len(set(normalized)) != 8:
                    raise QuestionGenerationError("本次模拟面试生成了重复问题")
                if any(key in excluded_keys for key in normalized):
                    raise QuestionGenerationError("本次模拟面试与历史问题重复")
                if not self._has_chinese_questions(generated):
                    raise QuestionGenerationError("模拟面试问题必须使用中文")
                return [item.model_dump(exclude_none=True) for item in generated]
            except QuestionGenerationError as error:
                last_error = error

        raise QuestionGenerationError("模拟面试题生成失败，请稍后重试") from last_error

    @staticmethod
    def _parse_questions(raw_content: str) -> list[GeneratedQuestion]:
        """Parse a JSON array, accepting an object wrapper for provider robustness."""

        try:
            payload: Any = json.loads(raw_content)
            if isinstance(payload, dict):
                payload = payload.get("questions")
            if not isinstance(payload, list) or not payload:
                raise ValueError("面试题结果必须是非空 JSON 数组")
            return [GeneratedQuestion.model_validate(item) for item in payload]
        except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as error:
            raise QuestionGenerationError("AI 返回的面试题不是有效 JSON") from error

    @staticmethod
    def _has_chinese_questions(questions: list[GeneratedQuestion]) -> bool:
        """Return whether generated question text contains Chinese natural language."""

        text = " ".join(item.question for item in questions)
        return any("\u4e00" <= character <= "\u9fff" for character in text)

    @staticmethod
    def _question_key(value: str) -> str:
        """Normalize whitespace and casing for reliable duplicate detection."""

        return "".join(value.split()).strip().lower()

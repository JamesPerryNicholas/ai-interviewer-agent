"""Business logic for interview sessions, chat persistence, and Redis context."""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import from_url
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.distributed_lock import acquire_lock, release_lock
from app.llm.deepseek import DeepSeekAPIError, DeepSeekClient
from app.models.evaluation_report import EvaluationReport
from app.models.interview import Interview
from app.models.job_position import JobPosition
from app.models.message import Message
from app.models.question import Question
from app.models.resume import Resume
from app.prompts.interview_chat_prompt import (
    build_answer_review_messages,
)
from app.schemas.interview import (
    InterviewChatResponse,
    InterviewHistoryResponse,
    InterviewListItem,
    InterviewResponse,
    InterviewStartResponse,
    MessageResponse,
)
from app.services.llm_usage_service import add_llm_usage
from app.services.question_service import QuestionGenerationError, QuestionService

logger = logging.getLogger(__name__)


class InterviewError(RuntimeError):
    """Base error for interview business rules."""


class InterviewResourceNotFoundError(InterviewError):
    """Raised when an interview resource is missing or not owned by the user."""


class InterviewNotActiveError(InterviewError):
    """Raised when a message is sent to a finished interview."""


class InterviewQuestionsRequiredError(InterviewError):
    """Raised when an interview starts before questions have been generated."""


class InterviewQuestionCountError(InterviewError):
    """Raised when a legacy question set is not the required eight questions."""


class InterviewAnswersRequiredError(InterviewError):
    """Raised when a session is ended before any valid answer is saved."""


class InterviewDuplicateRequestError(InterviewError):
    """Raised when a client retries an already accepted answer request."""


@dataclass(slots=True)
class StreamContext:
    """Immutable context captured before an SSE response starts."""

    interview_id: int
    user_id: int
    resume_analysis: dict[str, Any] | None
    job_description: str
    question_bank: list[str]
    history: list[dict[str, str]]
    current_question: str
    next_question: str | None
    answer_is_valid: bool
    answer_feedback: str
    should_finish: bool = False
    idempotent_content: str | None = None
    lock_client: Any = None
    lock_token: str | None = None


class InterviewService:
    """Coordinate database state, DeepSeek calls, and short-lived Redis context."""

    FINAL_MESSAGE = "好的，我的问题已经全部问完了。感谢你的回答，请点击“生成报告”查看本次面试结果。"

    def __init__(
        self,
        session: AsyncSession,
        deepseek_client: DeepSeekClient | None = None,
    ) -> None:
        self.session = session
        self.deepseek_client = deepseek_client or DeepSeekClient()

    async def start_interview(
        self,
        *,
        user_id: int,
        resume_id: int,
        job_id: int,
        request_id: str,
    ) -> InterviewStartResponse:
        """Serialize one idempotent start request across app workers."""

        lock_key = f"interview-start:{user_id}:{job_id}"
        client, token = await acquire_lock(lock_key, ttl_seconds=120)
        try:
            return await self._start_interview_locked(
                user_id=user_id,
                resume_id=resume_id,
                job_id=job_id,
                request_id=request_id,
            )
        finally:
            await release_lock(client, lock_key, token)

    async def _start_interview_locked(
        self,
        *,
        user_id: int,
        resume_id: int,
        job_id: int,
        request_id: str,
    ) -> InterviewStartResponse:
        """Create a session and persist the first generated question."""

        existing = await self.session.scalar(
            select(Interview).where(
                Interview.user_id == user_id,
                Interview.start_request_id == request_id,
            )
        )
        if existing is not None:
            first_message = await self.session.scalar(
                select(Message)
                .where(Message.interview_id == existing.id, Message.role == "assistant")
                .order_by(Message.id.asc())
                .limit(1)
            )
            job = await self.session.scalar(
                select(JobPosition).where(JobPosition.id == existing.job_id)
            )
            if first_message is None or job is None:
                raise InterviewError("面试创建请求尚未完整处理，请稍后重试")
            return InterviewStartResponse(
                interview=InterviewResponse.model_validate(existing).model_copy(
                    update={"position": job.position}
                ),
                first_message=MessageResponse.model_validate(first_message),
            )

        resume, job, questions = await self._load_owned_resources(
            user_id=user_id, resume_id=resume_id, job_id=job_id
        )
        if False and not questions:
            raise InterviewQuestionsRequiredError(
                "Generate interview questions before starting a session"
            )
        if False and len(questions) != 8:
            raise InterviewQuestionCountError(
                "当前岗位仍是旧版面试题，请重新生成 8 个面试问题后再开始"
            )

        question_snapshot = [
            {
                "id": question.id,
                "question": question.question,
                "category": question.category,
                "difficulty": question.difficulty,
            }
            for question in questions
        ]
        # The preparation-page question set is reference-only. Generate and
        # snapshot a fresh set for every newly started simulation.
        try:
            async with asyncio.timeout(75):
                question_snapshot = await QuestionService(self.session).generate_simulation_questions(
                    resume_id=resume_id,
                    job_id=job_id,
                    user_id=user_id,
                )
        except TimeoutError as error:
            raise QuestionGenerationError("模拟面试题生成超时，请稍后重试") from error
        interview = Interview(
            user_id=user_id,
            resume_id=resume_id,
            job_id=job_id,
            total_questions=len(question_snapshot),
            question_snapshot=question_snapshot,
            start_request_id=request_id,
        )
        self.session.add(interview)
        await self.session.flush()

        first_message = Message(
            interview_id=interview.id,
            role="assistant",
            content=question_snapshot[0]["question"],
            token_count=self._estimate_tokens(question_snapshot[0]["question"]),
        )
        self.session.add(first_message)
        await self.session.commit()
        await self.session.refresh(interview)
        await self.session.refresh(first_message)

        await self._cache_context(
            interview=interview,
            messages=[first_message],
            current_question=question_snapshot[0]["question"],
        )
        return InterviewStartResponse(
            interview=InterviewResponse.model_validate(interview).model_copy(
                update={
                    "position": job.position,
                    "completed_questions": interview.completed_questions,
                    "total_questions": interview.total_questions,
                }
            ),
            first_message=MessageResponse.model_validate(first_message),
        )

    async def chat(
        self,
        *,
        user_id: int,
        interview_id: int,
        content: str,
        request_id: str,
    ) -> InterviewChatResponse:
        """Serialize candidate messages for one interview."""

        lock_key = f"interview-chat:{interview_id}"
        client, token = await acquire_lock(lock_key)
        try:
            return await self._chat_locked(
                user_id=user_id,
                interview_id=interview_id,
                content=content,
                request_id=request_id,
            )
        finally:
            await release_lock(client, lock_key, token)

    async def _chat_locked(
        self,
        *,
        user_id: int,
        interview_id: int,
        content: str,
        request_id: str,
    ) -> InterviewChatResponse:
        """Persist a candidate answer, call DeepSeek, and persist its follow-up."""

        context = await self._prepare_candidate_message(
            user_id=user_id,
            interview_id=interview_id,
            content=content,
            request_id=request_id,
        )
        if context.get("idempotent_message") is not None:
            return InterviewChatResponse(
                interview_id=interview_id,
                message=MessageResponse.model_validate(context["idempotent_message"]),
            )
        if context["should_finish"]:
            final_message = await self._save_assistant_message(
                interview_id, self.FINAL_MESSAGE
            )
            await self._cache_interview_by_id(interview_id)
            return InterviewChatResponse(
                interview_id=interview_id,
                message=MessageResponse.model_validate(final_message),
            )

        assistant_content = self._compose_controlled_interviewer_reply(
            answer_is_valid=context["answer_is_valid"],
            answer_feedback=context["answer_feedback"],
            current_question=context["current_question"],
            next_question=context["next_question"],
        )
        assistant_message = await self._save_assistant_message(interview_id, assistant_content)
        await self._cache_interview_by_id(interview_id)
        return InterviewChatResponse(
            interview_id=interview_id,
            message=MessageResponse.model_validate(assistant_message),
        )

    async def get_history(self, *, user_id: int, interview_id: int) -> InterviewHistoryResponse:
        """Return one owned interview and its messages in chronological order."""

        interview = await self._get_owned_interview(user_id=user_id, interview_id=interview_id)
        job = await self.session.scalar(
            select(JobPosition).where(JobPosition.id == interview.job_id)
        )
        question_result = await self.session.execute(
            select(Question)
            .where(Question.job_id == interview.job_id)
            .order_by(Question.id.asc())
        )
        questions = list(question_result.scalars().all())
        messages = await self._get_messages(interview_id)
        total_questions = interview.total_questions or len(interview.question_snapshot) or len(questions)
        valid_answer_count = await self._count_valid_answers(interview_id)
        completed_questions = min(valid_answer_count, total_questions)
        was_dirty = (
            interview.total_questions != total_questions
            or interview.completed_questions != completed_questions
            or interview.current_question_index != completed_questions
        )
        if interview.total_questions == 0:
            interview.total_questions = total_questions
        interview.completed_questions = completed_questions
        interview.current_question_index = completed_questions
        # "ended_early" is an explicit user action. Do not reopen this kind
        # of interview merely because it has fewer than all planned answers.
        if completed_questions < total_questions and interview.status == "completed":
            interview.status = "in_progress"
            interview.end_time = None
            was_dirty = True
        elif completed_questions >= total_questions and interview.status != "completed":
            interview.status = "completed"
            interview.end_time = interview.end_time or datetime.now(timezone.utc)
            was_dirty = True
        if was_dirty:
            await self.session.commit()
        return InterviewHistoryResponse(
            interview=InterviewResponse.model_validate(interview).model_copy(
                update={
                    "position": job.position if job else None,
                    "completed_questions": completed_questions,
                    "total_questions": total_questions,
                }
            ),
            messages=[MessageResponse.model_validate(message) for message in messages],
        )

    async def end_early(self, *, user_id: int, interview_id: int) -> Interview:
        """Explicitly close an active interview before all questions are answered.

        The separate status keeps the reconciliation logic from reopening the
        session on the next history request. A partial report can then be
        generated from the answers that were actually completed.
        """

        interview = await self._get_owned_interview(user_id=user_id, interview_id=interview_id)
        valid_answer_count = await self._count_valid_answers(interview_id)
        if interview.status == "ended_early":
            if valid_answer_count:
                return interview
            # Recover a previous failed early-end attempt. The caller will
            # receive a clear validation error and the session stays active.
            interview.status = "in_progress"
            interview.end_time = None
            await self.session.commit()
            raise InterviewAnswersRequiredError("请至少回答一道面试问题后再结束面试")
        if interview.status == "completed":
            return interview
        if interview.status != "in_progress":
            raise InterviewNotActiveError("本次面试已结束")

        if valid_answer_count == 0:
            raise InterviewAnswersRequiredError("请至少回答一道面试问题后再结束面试")

        total_questions = interview.total_questions or len(interview.question_snapshot or [])
        interview.completed_questions = min(valid_answer_count, total_questions)
        interview.current_question_index = interview.completed_questions
        interview.status = "ended_early"
        interview.end_time = datetime.now(timezone.utc)
        # Do not commit here. The evaluation service commits the status and
        # report together, so a DeepSeek failure cannot leave a false ended state.
        await self.session.flush()
        return interview

    async def list_interviews(self, *, user_id: int) -> list[InterviewListItem]:
        """Return compact owned interview rows for the dashboard."""

        result = await self.session.execute(
            select(Interview, JobPosition.position, EvaluationReport.id, EvaluationReport.total_score)
            .join(JobPosition, JobPosition.id == Interview.job_id)
            .outerjoin(EvaluationReport, EvaluationReport.interview_id == Interview.id)
            .where(Interview.user_id == user_id)
            .order_by(Interview.start_time.desc(), Interview.id.desc())
        )
        return [
            InterviewListItem(
                id=interview.id,
                position=position,
                status=interview.status,
                start_time=interview.start_time,
                end_time=interview.end_time,
                report_id=report_id,
                total_score=total_score,
            )
            for interview, position, report_id, total_score in result.all()
        ]

    async def recall_message(
        self,
        *,
        user_id: int,
        interview_id: int,
        message_id: int,
    ) -> InterviewHistoryResponse:
        """Recall a user's message and invalidate its downstream AI context."""

        await self._get_owned_interview(user_id=user_id, interview_id=interview_id)
        message = await self.session.scalar(
            select(Message).where(
                Message.id == message_id,
                Message.interview_id == interview_id,
            )
        )
        if message is None:
            raise InterviewResourceNotFoundError("未找到消息")
        if message.role != "user":
            raise InterviewError("只能撤回用户发送的消息")

        # Every later message may have been generated from the recalled answer,
        # so remove the whole downstream branch, including the AI reply.
        await self.session.execute(
            delete(Message).where(
                Message.interview_id == interview_id,
                Message.id >= message_id,
            )
        )
        await self.session.commit()
        await self._cache_interview_by_id(interview_id)
        return await self.get_history(user_id=user_id, interview_id=interview_id)

    async def prepare_stream_chat(
        self,
        *,
        user_id: int,
        interview_id: int,
        content: str,
        request_id: str,
    ) -> StreamContext:
        """Save the candidate message before the HTTP stream begins."""

        lock_key = f"interview-chat:{interview_id}"
        client, token = await acquire_lock(lock_key)
        try:
            context = await self._prepare_candidate_message(
                user_id=user_id,
                interview_id=interview_id,
                content=content,
                request_id=request_id,
            )
        except Exception:
            await release_lock(client, lock_key, token)
            raise
        if context.get("idempotent_message") is not None:
            return StreamContext(
                interview_id=interview_id,
                user_id=user_id,
                resume_analysis=None,
                job_description="",
                question_bank=[],
                history=[],
                current_question="",
                next_question=None,
                answer_is_valid=True,
                answer_feedback="",
                idempotent_content=context["idempotent_message"].content,
                lock_client=client,
                lock_token=token,
            )
        return StreamContext(
            interview_id=interview_id,
            user_id=user_id,
            resume_analysis=context["resume_analysis"],
            job_description=context["job_description"],
            question_bank=context["question_bank"],
            history=context["history"],
            current_question=context["current_question"],
            next_question=context["next_question"],
            answer_is_valid=context["answer_is_valid"],
            answer_feedback=context["answer_feedback"],
            should_finish=context["should_finish"],
            lock_client=client,
            lock_token=token,
        )

    async def stream_response(self, context: StreamContext):
        """Hold the per-interview lock until streaming and persistence finish."""

        try:
            async for chunk in self._stream_response_locked(context):
                yield chunk
        finally:
            if context.lock_client is not None and context.lock_token is not None:
                await release_lock(
                    context.lock_client,
                    f"interview-chat:{context.interview_id}",
                    context.lock_token,
                )

    async def _stream_response_locked(self, context: StreamContext):
        """Yield DeepSeek chunks and save the complete assistant message at the end."""

        if context.idempotent_content is not None:
            for offset in range(0, len(context.idempotent_content), 2):
                yield context.idempotent_content[offset : offset + 2]
                await asyncio.sleep(0.02)
            return

        if context.should_finish:
            for offset in range(0, len(self.FINAL_MESSAGE), 2):
                yield self.FINAL_MESSAGE[offset : offset + 2]
                await asyncio.sleep(0.045)
            await self._save_assistant_message(context.interview_id, self.FINAL_MESSAGE)
            await self._cache_interview_by_id(context.interview_id)
            return

        # The private answer review is the only model call needed for this
        # turn. A second model call previously delayed the first visible word
        # and could invent a question outside the immutable eight-question
        # snapshot. Build the transition deterministically from that snapshot.
        assistant_content = self._build_controlled_interviewer_reply(context)
        for offset in range(0, len(assistant_content), 2):
            yield assistant_content[offset : offset + 2]
            await asyncio.sleep(0.035)
        await self._save_assistant_message(context.interview_id, assistant_content)
        await self._cache_interview_by_id(context.interview_id)
        return

    @staticmethod
    def _build_controlled_interviewer_reply(context: StreamContext) -> str:
        """Return feedback without allowing a model-invented extra question."""

        return InterviewService._compose_controlled_interviewer_reply(
            answer_is_valid=context.answer_is_valid,
            answer_feedback=context.answer_feedback,
            current_question=context.current_question,
            next_question=context.next_question,
        )

    @staticmethod
    def _compose_controlled_interviewer_reply(
        *,
        answer_is_valid: bool,
        answer_feedback: str,
        current_question: str,
        next_question: str | None,
    ) -> str:
        """Compose one strict interview transition from persisted state."""

        feedback = answer_feedback.strip().rstrip("。！？!?；;，,")
        if answer_is_valid:
            prefix = feedback or "好的，我了解了你的思路"
            if next_question:
                return f"{prefix}。我们继续下一个问题：{next_question}"
            return InterviewService.FINAL_MESSAGE

        prefix = feedback or "你的回答还没有充分回应当前问题，请补充具体做法和依据"
        return f"{prefix}。请继续回答当前问题：{current_question}"

    async def _load_owned_resources(
        self,
        *,
        user_id: int,
        resume_id: int,
        job_id: int,
    ) -> tuple[Resume, JobPosition, list[Question]]:
        resume = await self.session.scalar(
            select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
        )
        job = await self.session.scalar(
            select(JobPosition).where(JobPosition.id == job_id, JobPosition.user_id == user_id)
        )
        if resume is None or job is None:
            raise InterviewResourceNotFoundError("未找到简历或岗位")

        result = await self.session.execute(
            select(Question)
            .where(Question.job_id == job_id)
            .order_by(Question.id.asc())
        )
        return resume, job, list(result.scalars().all())

    async def _get_owned_interview(
        self, *, user_id: int, interview_id: int, for_update: bool = False
    ) -> Interview:
        statement = select(Interview).where(
            Interview.id == interview_id, Interview.user_id == user_id
        )
        if for_update:
            statement = statement.with_for_update()
        interview = await self.session.scalar(statement)
        if interview is None:
            raise InterviewResourceNotFoundError("未找到面试记录")
        return interview

    async def _prepare_candidate_message(
        self,
        *,
        user_id: int,
        interview_id: int,
        content: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Review an answer, advance only when valid, and build LLM context."""

        interview = await self._get_owned_interview(
            user_id=user_id, interview_id=interview_id, for_update=True
        )
        normalized_content = content.strip()
        if not normalized_content:
            raise InterviewError("消息内容不能为空")

        duplicate = await self.session.scalar(
            select(Message).where(
                Message.interview_id == interview_id,
                Message.client_request_id == request_id,
            )
        )
        if duplicate is not None:
            existing_reply = await self.session.scalar(
                select(Message)
                .where(
                    Message.interview_id == interview_id,
                    Message.role == "assistant",
                    Message.id > duplicate.id,
                )
                .order_by(Message.id.asc())
                .limit(1)
            )
            if existing_reply is None:
                raise InterviewDuplicateRequestError("该回答正在处理中，请稍后重试")
            return {"idempotent_message": existing_reply}

        if interview.status != "in_progress":
            raise InterviewNotActiveError("本次面试已结束，无法继续回答")

        resume, job, questions = await self._load_owned_resources(
            user_id=user_id,
            resume_id=interview.resume_id,
            job_id=interview.job_id,
        )
        if not questions and not interview.question_snapshot:
            raise InterviewError("当前面试没有可用的面试题")

        interview_questions = self._get_interview_questions(interview, questions)
        if not interview_questions:
            raise InterviewError("当前面试没有可用的面试题")

        valid_answer_count = await self._count_valid_answers(interview_id)
        interview.completed_questions = min(valid_answer_count, len(interview_questions))
        interview.current_question_index = interview.completed_questions
        if interview.completed_questions < len(interview_questions) and interview.status == "completed":
            interview.status = "in_progress"
            interview.end_time = None

        current_index = min(interview.current_question_index, len(interview_questions) - 1)
        current_question = interview_questions[current_index]["question"]
        answer_is_valid, answer_feedback = await self._review_answer(
            user_id=user_id,
            current_question=current_question,
            answer=normalized_content,
            resume_analysis=resume.extracted_info,
        )
        self.session.add(
            Message(
                interview_id=interview_id,
                role="user",
                content=normalized_content,
                token_count=self._estimate_tokens(normalized_content),
                is_valid_answer=answer_is_valid,
                client_request_id=request_id,
            )
        )

        if answer_is_valid:
            interview.completed_questions = min(len(interview_questions), valid_answer_count + 1)
            interview.current_question_index = min(current_index + 1, len(interview_questions))

        should_finish = interview.completed_questions >= len(interview_questions)
        if should_finish:
            interview.status = "completed"
            interview.end_time = datetime.now(timezone.utc)

        # Keep the candidate message and progress in the same transaction as
        # the assistant response. A failed/disconnected stream is therefore
        # rolled back instead of silently consuming one interview question.
        await self.session.flush()
        history = await self._get_messages(interview_id)
        next_question = (
            interview_questions[interview.current_question_index]["question"]
            if interview.current_question_index < len(interview_questions)
            else None
        )
        return {
            "resume_analysis": resume.extracted_info,
            "job_description": job.description,
            "question_bank": [question["question"] for question in interview_questions],
            "current_question": current_question,
            "next_question": next_question,
            "answer_is_valid": answer_is_valid,
            "answer_feedback": answer_feedback,
            "history": [
                {"role": message.role, "content": message.content} for message in history
            ],
            "should_finish": should_finish,
        }

    @staticmethod
    def _get_interview_questions(
        interview: Interview,
        current_questions: list[Question],
    ) -> list[dict[str, Any]]:
        """Use the question set captured when the interview was started."""

        if interview.question_snapshot:
            return interview.question_snapshot
        return [
            {
                "id": question.id,
                "question": question.question,
                "category": question.category,
                "difficulty": question.difficulty,
            }
            for question in current_questions
        ]

    async def _review_answer(
        self,
        *,
        user_id: int,
        current_question: str,
        answer: str,
        resume_analysis: dict[str, Any] | None,
    ) -> tuple[bool, str]:
        """Use a private AI rubric to decide whether the current question is answered."""

        # A truthful statement that the candidate has not done something is
        # still a direct answer to an experience-based interview question.
        # Handle it locally so an LLM cannot repeatedly reject the same answer
        # and trap the candidate in an endless follow-up loop.
        if self._is_explicit_experience_gap(answer):
            return True, "了解，你目前没有直接参与过这类工作。我们换一个角度继续了解你的相关经历"

        try:
            raw_content = await self.deepseek_client.chat_completion(
                messages=build_answer_review_messages(
                    resume_analysis=resume_analysis,
                    current_question=current_question,
                    answer=answer,
                ),
                model=settings.deepseek_model,
                # deepseek-v4-pro may reject response_format/json mode.
                # The prompt still requires JSON and the parser is defensive.
                json_mode=False,
                allow_reasoning_json_fallback=True,
                max_tokens=96,
                temperature=0.0,
            )
        except DeepSeekAPIError:
            # Answer review is an auxiliary guard, not the interview itself.
            # A temporary upstream failure must not turn a valid interview
            # answer into an HTTP 502 and block the whole session.
            logger.warning("Answer review upstream failed; using local fallback")
            return self._fallback_answer_review(answer)
        add_llm_usage(
            self.session,
            client=self.deepseek_client,
            user_id=user_id,
            feature="interview_answer_review",
        )
        is_valid, feedback = self._parse_answer_review(raw_content)
        # A malformed provider payload is different from an explicit AI
        # judgment that the answer is invalid. Treat only the former as a
        # fallback so a provider formatting glitch cannot create a phantom
        # extra question.
        if not is_valid and feedback.startswith("请围绕当前问题补充"):
            return self._fallback_answer_review(answer)
        return is_valid, feedback

    @staticmethod
    def _fallback_answer_review(answer: str) -> tuple[bool, str]:
        """Keep the interview moving when the private reviewer is unavailable."""

        if InterviewService._is_explicit_experience_gap(answer):
            return True, "了解，你目前没有直接参与过这类工作。我们换一个角度继续了解你的相关经历"

        compact = "".join(answer.split())
        is_substantive = len(compact) >= 16 and not compact.isdigit()
        if is_substantive:
            return True, "回答包含了具体思路，我们继续面试"
        return False, "回答内容还比较简略，请补充具体做法、原因或实际结果"

    @staticmethod
    def _is_explicit_experience_gap(answer: str) -> bool:
        """Recognize honest lack-of-experience answers as valid responses."""

        normalized = "".join(answer.casefold().split())
        experience_gap_phrases = (
            "没有参与过",
            "未参与过",
            "没参与过",
            "没有做过",
            "未做过",
            "没做过",
            "没有相关经验",
            "暂无相关经验",
            "没有这方面经验",
            "没有接触过",
            "未接触过",
            "没接触过",
            "没有经历过",
            "未经历过",
            "没经历过",
        )
        return any(phrase in normalized for phrase in experience_gap_phrases)

    @staticmethod
    def _parse_answer_review(raw_content: str) -> tuple[bool, str]:
        """Parse the private answer-review response without breaking the interview."""

        content = raw_content.strip().replace("```json", "").replace("```", "").strip()
        payload: Any = None
        candidates = [content]
        object_start = content.find("{")
        object_end = content.rfind("}")
        if object_start >= 0 and object_end > object_start:
            candidates.append(content[object_start : object_end + 1])

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and "is_valid" in parsed:
                payload = parsed
                break

        if payload is None:
            logger.warning("DeepSeek returned an invalid answer-review payload")
            return False, "请围绕当前问题补充更具体的说明后再继续。"

        raw_is_valid = payload["is_valid"]
        if isinstance(raw_is_valid, bool):
            is_valid = raw_is_valid
        else:
            normalized = str(raw_is_valid).strip().casefold()
            if normalized in {"true", "1", "yes", "是"}:
                is_valid = True
            elif normalized in {"false", "0", "no", "否"}:
                is_valid = False
            else:
                logger.warning("DeepSeek returned an unsupported is_valid value")
                return False, "请围绕当前问题补充更具体的说明后再继续。"
        feedback = str(payload.get("feedback") or "").strip()
        return is_valid, feedback[:500]

    async def _save_assistant_message(self, interview_id: int, content: str) -> Message:
        message = Message(
            interview_id=interview_id,
            role="assistant",
            content=content.strip(),
            token_count=self._estimate_tokens(content),
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def _get_messages(self, interview_id: int) -> list[Message]:
        result = await self.session.execute(
            select(Message)
            .where(Message.interview_id == interview_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return list(result.scalars().all())

    async def _count_valid_answers(self, interview_id: int) -> int:
        """Count only substantive candidate answers for progress tracking."""

        count = await self.session.scalar(
            select(func.count(Message.id)).where(
                Message.interview_id == interview_id,
                Message.role == "user",
                Message.is_valid_answer.is_not(False),
            )
        )
        return int(count or 0)

    async def _cache_interview_by_id(self, interview_id: int) -> None:
        interview = await self.session.scalar(select(Interview).where(Interview.id == interview_id))
        if interview is not None:
            await self._cache_context(
                interview=interview,
                messages=await self._get_messages(interview_id),
                current_question=await self._last_assistant_content(interview_id),
            )

    async def _last_assistant_content(self, interview_id: int) -> str | None:
        result = await self.session.execute(
            select(Message.content)
            .where(Message.interview_id == interview_id, Message.role == "assistant")
            .order_by(Message.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _cache_context(
        self,
        *,
        interview: Interview,
        messages: list[Message],
        current_question: str | None,
    ) -> None:
        """Cache resumable session context without making Redis a hard dependency."""

        context = {
            "current_question": current_question,
            "history": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "status": interview.status,
        }
        try:
            async with from_url(settings.redis_url, decode_responses=True) as client:
                await client.set(
                    f"interview:{interview.id}:context",
                    json.dumps(context, ensure_ascii=False),
                    ex=86_400,
                )
        except Exception:
            logger.exception("Unable to cache interview context in Redis")

    @staticmethod
    def _estimate_tokens(content: str) -> int:
        """Store a lightweight estimate until provider usage metadata is available."""

        return max(1, len(content.split()))

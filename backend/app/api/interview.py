"""Authenticated interview preparation and live chat routes."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.rate_limit import enforce_rate_limit, refund_rate_limit
from app.database.session import get_db_session
from app.llm.deepseek import DeepSeekAPIError, DeepSeekConfigurationError
from app.models.user import User
from app.schemas.evaluation import InterviewFinishResponse
from app.schemas.interview import (
    InterviewChatRequest,
    InterviewChatResponse,
    InterviewHistoryResponse,
    InterviewListItem,
    InterviewStartRequest,
    InterviewStartResponse,
)
from app.schemas.question import GenerateQuestionsRequest, QuestionResponse
from app.services.evaluation_service import (
    EvaluationError,
    EvaluationNotReadyError,
    EvaluationResourceNotFoundError,
    EvaluationService,
)
from app.services.interview_service import (
    InterviewAnswersRequiredError,
    InterviewError,
    InterviewNotActiveError,
    InterviewQuestionCountError,
    InterviewQuestionsRequiredError,
    InterviewResourceNotFoundError,
    InterviewService,
)
from app.services.question_service import (
    QuestionGenerationError,
    QuestionResourceNotFoundError,
    QuestionService,
    ResumeAnalysisRequiredError,
)

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.post("/start", response_model=InterviewStartResponse, status_code=status.HTTP_201_CREATED)
async def start_interview(
    payload: InterviewStartRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InterviewStartResponse:
    """Create an owned interview and return its first generated question."""

    limit_consumed = False
    created = False
    try:
        await enforce_rate_limit(
            "interview-start", str(current_user.id), limit=20, window_seconds=3600
        )
        limit_consumed = True
        result = await InterviewService(session).start_interview(
            user_id=current_user.id,
            resume_id=payload.resume_id,
            job_id=payload.job_id,
            request_id=payload.request_id,
        )
        created = True
        return result
    except InterviewQuestionsRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="您还未为当前岗位生成面试题，请先完成简历分析并生成面试题",
        ) from error
    except InterviewQuestionCountError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except InterviewResourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到简历或岗位",
        ) from error


    except QuestionResourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到简历或岗位",
        ) from error
    except ResumeAnalysisRequiredError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except DeepSeekConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DeepSeek API 尚未配置",
        ) from error
    except DeepSeekAPIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="模拟面试题生成失败，请稍后重试",
        ) from error
    except QuestionGenerationError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    finally:
        if limit_consumed and not created:
            await refund_rate_limit("interview-start", str(current_user.id))


@router.post("/chat", response_model=InterviewChatResponse)
async def interview_chat(
    payload: InterviewChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InterviewChatResponse:
    """Send one answer and receive a persisted assistant follow-up."""

    try:
        await enforce_rate_limit(
            "interview-chat", str(current_user.id), limit=120, window_seconds=3600
        )
        return await InterviewService(session).chat(
            user_id=current_user.id,
            interview_id=payload.interview_id,
            content=payload.message,
            request_id=payload.request_id,
        )
    except InterviewResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到面试记录") from error
    except InterviewNotActiveError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except InterviewAnswersRequiredError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except InterviewError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except DeepSeekConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DeepSeek API 尚未配置",
        ) from error
    except DeepSeekAPIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 面试官暂时不可用，请稍后重试",
        ) from error
@router.get("/history/{interview_id}", response_model=InterviewHistoryResponse)
async def interview_history(
    interview_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InterviewHistoryResponse:
    """Return a user's interview and all saved messages."""

    try:
        return await InterviewService(session).get_history(
            user_id=current_user.id,
            interview_id=interview_id,
        )
    except InterviewResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到面试记录") from error


@router.get("/list", response_model=list[InterviewListItem])
async def list_interviews(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[InterviewListItem]:
    """Return the authenticated user's interview history for the dashboard."""

    return await InterviewService(session).list_interviews(user_id=current_user.id)


@router.post("/{interview_id}/finish", response_model=InterviewFinishResponse)
async def finish_interview(
    interview_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InterviewFinishResponse:
    """Finish an interview and generate its AI evaluation report."""

    try:
        await enforce_rate_limit(
            "interview-evaluation", str(current_user.id), limit=8, window_seconds=3600
        )
        report = await EvaluationService(session).evaluate_interview(
            user_id=current_user.id,
            interview_id=interview_id,
        )
        interview = await InterviewService(session).get_history(
            user_id=current_user.id,
            interview_id=interview_id,
        )
        return InterviewFinishResponse(interview=interview.interview, report=report)
    except EvaluationResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except EvaluationNotReadyError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except DeepSeekConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DeepSeek API未配置",
        ) from error
    except (DeepSeekAPIError, EvaluationError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="面试评分生成失败，请稍后重试",
        ) from error


@router.post("/{interview_id}/end", response_model=InterviewFinishResponse)
async def end_interview_early(
    interview_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InterviewFinishResponse:
    """End an interview on the candidate's request and score saved answers."""

    try:
        await enforce_rate_limit(
            "interview-evaluation", str(current_user.id), limit=8, window_seconds=3600
        )
        await InterviewService(session).end_early(
            user_id=current_user.id,
            interview_id=interview_id,
        )
        report = await EvaluationService(session).evaluate_interview(
            user_id=current_user.id,
            interview_id=interview_id,
            allow_partial=True,
        )
        interview = await InterviewService(session).get_history(
            user_id=current_user.id,
            interview_id=interview_id,
        )
        return InterviewFinishResponse(interview=interview.interview, report=report)
    except EvaluationResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except EvaluationNotReadyError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except InterviewNotActiveError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except InterviewAnswersRequiredError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except DeepSeekConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DeepSeek API 尚未配置",
        ) from error
    except (DeepSeekAPIError, EvaluationError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="面试评分生成失败，请稍后重试",
        ) from error


@router.delete(
    "/{interview_id}/messages/{message_id}",
    response_model=InterviewHistoryResponse,
)
async def recall_interview_message(
    interview_id: int,
    message_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InterviewHistoryResponse:
    """Recall an owned user message and its downstream AI response branch."""

    try:
        return await InterviewService(session).recall_message(
            user_id=current_user.id,
            interview_id=interview_id,
            message_id=message_id,
        )
    except InterviewResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到消息") from error
    except InterviewError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/stream")
async def interview_stream(
    payload: InterviewChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StreamingResponse:
    """Stream the assistant follow-up as Server-Sent Events."""

    service = InterviewService(session)
    try:
        await enforce_rate_limit(
            "interview-chat", str(current_user.id), limit=120, window_seconds=3600
        )
        context = await service.prepare_stream_chat(
            user_id=current_user.id,
            interview_id=payload.interview_id,
            content=payload.message,
            request_id=payload.request_id,
        )
    except InterviewResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到面试记录") from error
    except InterviewNotActiveError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except InterviewError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except DeepSeekConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DeepSeek API 尚未配置",
        ) from error
    except DeepSeekAPIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 面试官暂时不可用，请稍后重试",
        ) from error

    if not service.deepseek_client.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DeepSeek API 尚未配置",
        )

    async def event_stream():
        try:
            async for chunk in service.stream_response(context):
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except DeepSeekConfigurationError:
            yield f"data: {json.dumps({'error': 'DeepSeek API 尚未配置'}, ensure_ascii=False)}\n\n"
        except (DeepSeekAPIError, InterviewError):
            yield f"data: {json.dumps({'error': 'AI 面试官暂时不可用，请稍后重试'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/generate", response_model=list[QuestionResponse])
async def generate_interview_questions(
    payload: GenerateQuestionsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[QuestionResponse]:
    """Generate personalized questions using the user's analyzed resume and job."""

    try:
        await enforce_rate_limit(
            "question-generation", str(current_user.id), limit=10, window_seconds=3600
        )
        return await QuestionService(session).generate_questions(
            resume_id=payload.resume_id,
            job_id=payload.job_id,
            user_id=current_user.id,
        )
    except QuestionResourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到简历或岗位",
        ) from error
    except ResumeAnalysisRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先完成简历分析，再生成面试题",
        ) from error
    except DeepSeekConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DeepSeek API 尚未配置",
        ) from error
    except (DeepSeekAPIError, QuestionGenerationError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="面试题生成失败，请稍后重试",
        ) from error

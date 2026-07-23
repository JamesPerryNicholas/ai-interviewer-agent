"""Application service for DeepSeek-powered resume analysis."""

import json
import re
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.distributed_lock import acquire_lock, release_lock
from app.llm.deepseek import DeepSeekClient, DeepSeekError
from app.models.resume import Resume
from app.prompts.resume_prompt import build_resume_analysis_messages
from app.schemas.resume import ResumeAnalysisResponse
from app.services.llm_usage_service import add_llm_usage


class ResumeAnalysisError(RuntimeError):
    """Raised when the model output cannot become a capability profile."""


class ResumeNotFoundError(ResumeAnalysisError):
    """Raised when the resume is missing or belongs to another user."""


class ResumeAnalysisService:
    """Analyze an owned resume and persist its structured capability profile."""

    def __init__(
        self,
        session: AsyncSession,
        deepseek_client: DeepSeekClient | None = None,
    ) -> None:
        self.session = session
        self.deepseek_client = deepseek_client or DeepSeekClient()

    async def analyze_resume(self, resume_id: int, user_id: int) -> ResumeAnalysisResponse:
        """Prevent concurrent analysis calls for the same resume."""

        lock_key = f"resume-analysis:{resume_id}"
        client, token = await acquire_lock(lock_key)
        try:
            return await self._analyze_resume_locked(resume_id, user_id)
        finally:
            await release_lock(client, lock_key, token)

    async def _analyze_resume_locked(
        self, resume_id: int, user_id: int
    ) -> ResumeAnalysisResponse:
        """Analyze one resume only when it belongs to the authenticated user."""

        result = await self.session.execute(
            select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
        )
        resume = result.scalar_one_or_none()
        if resume is None:
            raise ResumeNotFoundError("未找到简历")
        if not resume.content.strip():
            raise ResumeAnalysisError("简历中没有可解析的文本")
        if len(resume.content) > settings.max_resume_text_chars:
            raise ResumeAnalysisError("简历文本超过系统允许的最大长度")

        fallback_analysis: ResumeAnalysisResponse | None = None
        for attempt in range(2):
            messages = build_resume_analysis_messages(resume.content)
            if attempt:
                messages.append(
                    {
                        "role": "user",
                        "content": "请重新输出，experience、projects、suggestions必须使用简体中文。",
                    }
                )

            raw_content = await self.deepseek_client.chat_completion(
                messages=messages,
                model=settings.deepseek_model,
                # v4-pro can prioritize its reasoning channel when JSON mode is
                # enabled. We parse the JSON object defensively below instead.
                json_mode=False,
                allow_reasoning_json_fallback=True,
            )
            add_llm_usage(
                self.session,
                client=self.deepseek_client,
                user_id=user_id,
                feature="resume_analysis",
            )

            try:
                payload = self._extract_json_object(raw_content)
                analysis = ResumeAnalysisResponse.model_validate(self._normalize_payload(payload))
            except (json.JSONDecodeError, TypeError, ValidationError, ValueError) as error:
                if attempt == 1:
                    raise ResumeAnalysisError(
                        "DeepSeek returned invalid resume analysis JSON"
                    ) from error
                continue

            if fallback_analysis is None:
                fallback_analysis = analysis
            if attempt == 1 or self._has_chinese_text(analysis):
                break

        if fallback_analysis is None:
            raise ResumeAnalysisError("AI 没有返回有效的简历分析结果")
        if self._has_chinese_text(analysis):
            fallback_analysis = analysis
        analysis = fallback_analysis

        if not self._has_chinese_text(analysis):
            localized = await self._localize_analysis(analysis, user_id=user_id)
            if localized is not None and self._has_chinese_text(localized):
                analysis = localized

        resume.extracted_info = analysis.model_dump()
        await self.session.commit()
        await self.session.refresh(resume)
        return analysis

    @staticmethod
    def _extract_json_object(raw_content: str) -> dict[str, Any]:
        """Extract the last valid JSON object, including fenced model output."""

        decoder = json.JSONDecoder()
        parsed: dict[str, Any] | None = None
        for index, character in enumerate(raw_content):
            if character != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(raw_content[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                parsed = candidate
        if parsed is None:
            raise ValueError("AI 返回内容中没有找到有效 JSON 对象")
        return parsed

    @staticmethod
    def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """Keep the public schema stable when the model adds useful extra fields."""

        skills = payload.get("skills", [])
        if isinstance(skills, dict):
            skills = [
                item
                for values in skills.values()
                if isinstance(values, list)
                for item in values
                if isinstance(item, str)
            ]
        elif not isinstance(skills, list):
            skills = []

        projects = payload.get("projects", [])
        if not isinstance(projects, list):
            projects = []
        suggestions = payload.get("suggestions", [])
        if not isinstance(suggestions, list):
            suggestions = []

        return {
            "skills": [item for item in skills if isinstance(item, str)],
            "projects": [item for item in projects if isinstance(item, str)],
            "experience": str(payload.get("experience", "") or ""),
            "level": str(payload.get("level", "unknown") or "unknown"),
            "suggestions": [item for item in suggestions if isinstance(item, str)],
        }

    @staticmethod
    def _has_chinese_text(analysis: ResumeAnalysisResponse) -> bool:
        """Check whether the model followed the requested Chinese output language."""

        text = " ".join(
            [analysis.experience, *analysis.projects, *analysis.suggestions]
        )
        return any("\u4e00" <= character <= "\u9fff" for character in text)

    async def _localize_analysis(
        self,
        analysis: ResumeAnalysisResponse,
        user_id: int,
    ) -> ResumeAnalysisResponse | None:
        """Translate an otherwise valid model result without changing the configured model."""

        messages = [
            {
                "role": "system",
                "content": (
                    "你是中文简历能力画像本地化助手。请把输入对象中的所有自然语言重新改写为简体中文，"
                    "即使原文是英文也必须翻译，不能直接保留英文句子。Python、FastAPI、PostgreSQL、"
                    "Redis 等技术名词保留英文。只能返回一个合法JSON对象，只能包含skills、projects、"
                    "experience、level、suggestions五个字段；level只能使用entry、junior、mid、senior、"
                    "lead、unknown之一。禁止Markdown、表格、代码块和任何额外解释。输出前请自行检查JSON"
                    "可解析且experience、projects、suggestions中包含中文自然语言。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请将下面的能力画像严格本地化为简体中文，并只返回JSON：\n"
                    f"{json.dumps(analysis.model_dump(), ensure_ascii=False)}"
                ),
            },
        ]
        localized_result: ResumeAnalysisResponse | None = None
        for _ in range(2):
            try:
                raw_content = await self.deepseek_client.chat_completion(
                    messages=messages,
                    model=settings.deepseek_model,
                    json_mode=False,
                    max_tokens=2048,
                )
                add_llm_usage(
                    self.session,
                    client=self.deepseek_client,
                    user_id=user_id,
                    feature="resume_localization",
                )
                try:
                    payload = self._extract_json_object(raw_content)
                except ValueError:
                    try:
                        payload = self._extract_markdown_table(raw_content)
                    except ValueError:
                        payload = self._extract_markdown_profile(raw_content)
                localized_result = ResumeAnalysisResponse.model_validate(
                    self._normalize_payload(payload)
                )
                if self._has_chinese_text(localized_result):
                    return localized_result
            except (DeepSeekError, json.JSONDecodeError, TypeError, ValidationError, ValueError):
                continue
        return localized_result

    @staticmethod
    def _extract_markdown_table(raw_content: str) -> dict[str, Any]:
        """Parse the compact field/value table sometimes returned by the model."""

        values: dict[str, str] = {}
        for line in raw_content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|") or stripped.count("|") < 2:
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|", 1)]
            if len(cells) != 2 or cells[0].lower() in {"字段", "field", "------"}:
                continue
            key = cells[0].lower()
            if key in {"skills", "projects", "experience", "level", "suggestions"}:
                values[key] = cells[1]

        if not values:
            raise ValueError("No supported fields found in model table")

        def split_items(value: str) -> list[str]:
            items = re.split(r"<br\s*/?>|\n|(?=\d+\.\s)|(?=[-•]\s)", value)
            return [re.sub(r"^(?:\d+\.\s*|[-•]\s*)", "", item).strip() for item in items if item.strip()]

        return {
            "skills": [item.strip() for item in re.split(r"[,，、]", values.get("skills", "")) if item.strip()],
            "projects": split_items(values.get("projects", "")),
            "experience": values.get("experience", ""),
            "level": values.get("level", "unknown").strip(),
            "suggestions": split_items(values.get("suggestions", "")),
        }

    @staticmethod
    def _extract_markdown_profile(raw_content: str) -> dict[str, Any]:
        """Parse the heading/list format used by some v4-pro localization replies."""

        # Split by headings instead of relying on a multiline look-ahead. This
        # also handles headings followed by blank lines or bold formatting.
        sections: dict[str, str] = {}
        blocks = re.split(r"(?m)^##\s+", raw_content)
        for block in blocks[1:]:
            lines = block.splitlines()
            if not lines:
                continue
            title = re.sub(r"[*`]", "", lines[0]).strip().lower()
            sections[title] = "\n".join(lines[1:]).strip()

        def section(title: str) -> str:
            return sections.get(title.lower(), "")

        skills = [
            item.strip()
            for item in re.findall(r"^[-*]\s+(.+)$", section("技术栈"), flags=re.MULTILINE)
        ]
        projects = [
            re.sub(r"\s+", " ", item).strip()
            for item in re.findall(
                r"^\d+\.\s+(.*?)(?=\n\d+\.\s|\Z)",
                section("项目经验"),
                flags=re.MULTILINE | re.DOTALL,
            )
        ]
        suggestions = [
            item.strip()
            for item in re.findall(r"^[-*]\s+(.+)$", section("建议与提升方向"), flags=re.MULTILINE)
        ]
        experience = re.sub(r"[*`]", "", section("工作经历"))
        experience = re.sub(r"\s+", " ", experience).strip()
        level_match = re.search(r"级别.*?[：:]\s*\**([^*\n]+)", raw_content)
        level = (level_match.group(1).strip() if level_match else "unknown")
        level = {"初级": "junior", "中级": "mid", "高级": "senior", "入门": "entry"}.get(level, level)

        if not any((skills, projects, experience, suggestions)):
            raise ValueError("No supported fields found in markdown profile")
        return {
            "skills": skills,
            "projects": projects,
            "experience": experience,
            "level": level,
            "suggestions": suggestions,
        }

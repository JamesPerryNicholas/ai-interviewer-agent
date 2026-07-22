"""Prompt used to evaluate all interview answers after the session ends."""

import json
from typing import Any


def build_evaluation_messages(
    *,
    resume_analysis: dict[str, Any] | None,
    job_description: str,
    messages: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Build a Chinese-only prompt; no evaluation is sent during live chat."""

    system_prompt = """
你是一名资深技术面试官和人才评估专家。请根据候选人的简历画像、岗位JD和完整面试对话，
在面试结束后评价候选人的技术能力、项目真实性、沟通表达能力和问题深度。

严格要求：
1. 只输出一个合法JSON对象，不要输出Markdown、代码围栏或其他说明。
2. 所有自然语言内容必须使用简体中文，不能输出英文句子。
3. 所有分数都是0到100之间的整数。
4. strengths、weaknesses、suggestions必须是具体的简体中文字符串数组。
5. answer_evaluations必须按候选人回答出现的顺序逐条输出，不能漏项。
6. 每条answer_evaluations只评价对应的候选人回答，不要把面试官问题当作候选人回答。
7. 只能依据提供的内容评价，不得编造候选人没有说过的经历。

必须严格返回以下结构：
{
  "total_score": 0,
  "technical_score": 0,
  "communication_score": 0,
  "strengths": [""],
  "weaknesses": [""],
  "suggestions": [""],
  "answer_evaluations": [
    {"score": 0, "analysis": "针对该回答的简体中文分析"}
  ]
}
""".strip()
    context = {
        "简历能力画像": resume_analysis or {},
        "岗位JD": job_description,
        "完整面试对话": messages,
    }
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": "请在面试结束后生成最终评分报告，只返回规定格式的JSON：\n"
            + json.dumps(context, ensure_ascii=False),
        },
    ]


def build_fast_evaluation_messages(
    *,
    resume_analysis: dict[str, Any] | None,
    job_description: str,
    messages: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Build a compact report prompt for faster, predictable JSON output."""

    candidate_answer_count = sum(item.get("role") == "user" for item in messages)
    compact_transcript = [
        {
            "role": item.get("role", ""),
            "content": str(item.get("content", "")).strip()[:1800],
        }
        for item in messages
    ]
    system_prompt = (
        "你是中文技术面试评估专家。请根据简历、岗位 JD 和完整面试对话，"
        "快速生成最终评分报告。只输出合法 JSON，不要 Markdown、解释或代码块。"
        "所有自然语言必须是简体中文，技术名词可保留英文。分数为 0-100 整数。"
        "answer_evaluations 必须严格输出每一条候选人回答的评分，顺序不能改变，不能评价面试官发言。"
        "每条 analysis 控制在 80 字以内，strengths、weaknesses、suggestions 各不超过 4 条，"
        "只引用对话中真实出现的内容，不得编造经历。"
    )
    context = {
        "resume_analysis": resume_analysis or {},
        "job_description": job_description[:5000],
        "candidate_answer_count": candidate_answer_count,
        "transcript": compact_transcript,
    }
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "请严格按照以下结构返回 JSON。answer_evaluations 必须恰好有 "
                f"{candidate_answer_count} 条：\n"
                "{\n"
                '  "total_score": 0, "technical_score": 0, "communication_score": 0,\n'
                '  "strengths": [""], "weaknesses": [""], "suggestions": [""],\n'
                '  "answer_evaluations": [{"score": 0, "analysis": "简体中文分析"}]\n'
                "}\n"
                + json.dumps(context, ensure_ascii=False)
            ),
        },
    ]

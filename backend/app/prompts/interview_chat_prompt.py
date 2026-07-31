"""Prompt builders for multi-turn, industry-agnostic interview conversations."""

import json
from collections.abc import Sequence
from typing import Any


def build_answer_review_messages(
    *,
    resume_analysis: dict[str, Any] | None,
    current_question: str,
    answer: str,
) -> list[dict[str, str]]:
    """Build a private rubric prompt used to decide whether a question is answered."""

    # Resume analysis is intentionally not embedded here. The current
    # question and candidate answer are sufficient for relevance checking,
    # while sending the full resume on every turn adds several seconds of
    # prompt processing latency.
    del resume_analysis
    return [
        {
            "role": "system",
            "content": (
                "你是通用中文面试回答判定器，不是考试判卷器。"
                "判断候选人是否已经对当前面试问题作出直接或合理回应。"
                "候选人明确说明‘没有参与过’、‘没有做过’、‘暂无相关经验’、‘不了解’，"
                "如果这些内容正面回应了问题，必须判定为有效，面试官应尊重事实，不得反复追问同一段经历。"
                "候选人提供课程作业、个人项目、实习中的相近工作、模拟经历、观察经验、学习计划或可迁移经验，"
                "只要与当前问题相关，也判定为有效。简短但直接的‘是/否’或情况说明也可以有效。"
                "只有空白、纯符号、纯数字、明显答非所问、乱码，或完全没有回应问题时才判定为无效。"
                "只能返回合法JSON对象，不要输出Markdown或额外文字。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请按以下格式返回：{\"is_valid\":true或false,\"feedback\":\"简短中文反馈\"}\n"
                f"当前面试问题：{current_question}\n"
                f"候选人回答：{answer}"
            ),
        },
    ]


def build_interview_chat_messages(
    *,
    resume_analysis: dict[str, Any] | None,
    job_description: str,
    generated_questions: Sequence[str],
    history: Sequence[dict[str, str]],
    current_question: str,
    next_question: str | None,
    answer_is_valid: bool,
    answer_feedback: str,
) -> list[dict[str, str]]:
    """Build a grounded interviewer prompt from context and chat history."""

    system_prompt = (
        "你是一名严谨、友好的中文面试官。请围绕目标岗位进行真实的多轮面试，适用于技术、运营、销售、设计、教育、管理等不同岗位。"
        "所有回复必须使用简体中文；Python、FastAPI、RAG、SSE 等技术名词保留标准英文。"
        "回复要简洁、自然、像真实面试交流。不要输出JSON、标题、评分或问题列表。"
        "不要替候选人回答问题。这里是面试交流，不是考试或做题。"
        "严禁使用‘下一题’‘题目’‘做题’‘答题’‘题库’‘题号’‘正确答案’等考试式说法。"
        "只能使用‘当前问题’‘下一个问题’‘继续聊聊’‘请你介绍’等自然面试表达。"
    )

    if answer_is_valid:
        turn_instruction = (
            "候选人上一条回答已覆盖当前问题。可以用一句话给出自然的面试官反馈，"
            f"然后说‘我们继续下一个问题’，并完整询问下一个问题：{next_question or '面试已完成'}"
        )
    else:
        turn_instruction = (
            "候选人上一条回答没有覆盖当前问题。请礼貌指出还需要补充的方向，"
            f"然后最多补充询问当前问题一次：{current_question}。"
            "如果候选人已经明确说明没有相关经历，或给出了相关替代经历，不得再次重复当前问题，必须进入下一个问题。"
        )

    context = {
        "resume_analysis": resume_analysis or {},
        "job_description": job_description,
        "interview_questions": list(generated_questions),
    }
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "面试上下文：\n"
                f"{json.dumps(context, ensure_ascii=False)}\n\n"
                f"当前正式面试问题：{current_question}\n"
                f"回答判定反馈：{answer_feedback}\n"
                f"本轮处理要求：{turn_instruction}\n\n"
                "请根据以下对话历史继续面试，并使用简体中文回复。"
            ),
        },
    ]
    messages.extend({"role": item["role"], "content": item["content"]} for item in history)
    return messages

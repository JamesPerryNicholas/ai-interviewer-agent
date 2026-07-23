"""Answer-review parsing must not interrupt an active interview."""

from app.services.interview_service import InterviewService


def test_answer_review_parses_fenced_json():
    assert InterviewService._parse_answer_review(
        '```json\n{"is_valid": true, "feedback": "回答具体"}\n```'
    ) == (True, "回答具体")


def test_answer_review_extracts_json_from_extra_model_text():
    assert InterviewService._parse_answer_review(
        '判定结果如下：{"is_valid":"false","feedback":"需要补充项目细节"}。'
    ) == (False, "需要补充项目细节")


def test_answer_review_malformed_output_falls_back_without_exception():
    is_valid, feedback = InterviewService._parse_answer_review("暂时无法给出结构化结果")

    assert is_valid is False
    assert "补充" in feedback


def test_valid_answer_transitions_to_the_persisted_next_question_only():
    reply = InterviewService._compose_controlled_interviewer_reply(
        answer_is_valid=True,
        answer_feedback="回答覆盖了关键实现步骤",
        current_question="第七个问题",
        next_question="第八个且最后一个问题",
    )

    assert "第八个且最后一个问题" in reply
    assert "第九" not in reply


def test_invalid_answer_repeats_current_question_without_advancing():
    reply = InterviewService._compose_controlled_interviewer_reply(
        answer_is_valid=False,
        answer_feedback="回答过于简略",
        current_question="请说明缓存一致性方案",
        next_question="不应该出现的问题",
    )

    assert "请说明缓存一致性方案" in reply
    assert "不应该出现的问题" not in reply


def test_last_valid_answer_returns_final_message_without_an_extra_question():
    reply = InterviewService._compose_controlled_interviewer_reply(
        answer_is_valid=True,
        answer_feedback="回答完整",
        current_question="第八个问题",
        next_question=None,
    )

    assert reply == InterviewService.FINAL_MESSAGE

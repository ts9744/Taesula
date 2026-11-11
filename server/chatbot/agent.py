import json
import logging
import os
import re
import time

from ollama import Client

from . import sessions, tools

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b-instruct")
MAX_TOOL_ITERATIONS = 6

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = """당신은 물류 로봇 Taesula의 어시스턴트입니다.
창고 안 물품 재고를 조회하거나, 로봇을 자연어 명령으로 제어하는 역할을 합니다.

이동 명령의 의미 (move_robot):
로봇은 메카넘휠이라 회전하지 않고 항상 격자 위쪽을 바라본 채 평행이동합니다.
- forward: 앞(격자 위쪽)으로 이동
- backward: 뒤(격자 아래쪽)로 이동
- left: 왼쪽으로 옆걸음 이동 (제자리 회전이 아님)
- right: 오른쪽으로 옆걸음 이동 (제자리 회전이 아님)
- steps: 이동할 칸 수(1~5). "두 칸"처럼 칸 수를 말하면 steps에 넣고, 말하지 않으면 1칸입니다.
- 로봇은 정해진 칸만큼 가고 스스로 멈춥니다. 정지 명령은 따로 없습니다.
- move_robot 결과의 status가 "accepted"일 때만 "이동 명령을 보냈습니다"라고 답하세요.
  "rejected"이면 움직이지 않은 것이므로 결과의 message(이유)를 그대로 알리세요.

규칙:
- 반드시 제공된 도구(tool)를 사용해서 실제 DB/로봇 상태를 확인한 뒤 답하세요.
- 존재하지 않는 물품이나 QR 코드를 지어내지 마세요. 도구 결과가 "not found"이면 사용자에게 그대로 알리세요.
- 물품 하나에 대해 질문하면 list_items가 아니라 get_item_info(qr_code=...)를 사용하세요. list_items는
  "전체 물품 목록을 보여줘" 같이 목록 전체가 필요할 때만 사용합니다.
- 항상 한국어로, 간결하게 답하세요.

가장 중요한 규칙 (반드시 지킬 것):
사용자가 로봇을 움직이거나 물건을 보내달라고 요청하면, 그 요청에 답하는 매 턴마다 move_robot 또는 start_delivery
도구를 실제로 호출해야 합니다. 이전 턴에서 같은 물건을 이미 언급했거나 위치를 이미 알고 있더라도, "이동시켰습니다"
"보냈습니다" 같은 완료 표현을 쓰려면 반드시 이번 턴에 해당 도구 호출 결과가 있어야 합니다. 도구를 호출하지 않고
이동/전송이 완료됐다고 말하는 것은 절대 금지되며, 이는 실제로는 아무 일도 일어나지 않았는데 사용자를 속이는 것과
같습니다.

나쁜 예 (금지): 사용자가 "그 물건 거기로 보내줘"라고 했는데 도구 호출 없이 "boxA를 ZONE1로 이동시켰습니다"라고 답함.
좋은 예: 같은 요청에 대해 start_delivery(qr_code="boxA")를 호출한 뒤, 그 결과를 바탕으로 "boxA를 ZONE1로 보냈습니다"라고 답함.
"""

_client = Client(host=OLLAMA_HOST)

# qwen2.5 는 한국어로 지시해도 가끔 중국어로 답한다. 한 번 기록에 남으면 다음 턴부터 따라 하므로 막는다.
_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
KOREAN_RETRY_MESSAGE = {
    "role": "system",
    "content": "방금 답변에 중국어가 섞였습니다. 같은 내용을 한국어로만 다시 답하세요. 한자를 쓰지 마세요.",
}
NOT_KOREAN_REPLY = "답변을 한국어로 만들지 못했습니다. 다시 말씀해 주세요."


def _message_to_dict(message) -> dict:
    result = {"role": message.role, "content": message.content or ""}

    if message.tool_calls:
        result["tool_calls"] = [
            {
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                }
            }
            for call in message.tool_calls
        ]

    return result


def run_agent_turn(session_id: str, user_message: str) -> str:
    history = sessions.get_history(session_id)
    history.append({"role": "user", "content": user_message})

    reply = "요청을 처리하지 못했습니다. 다시 시도해주세요."
    turn_start = time.perf_counter()
    korean_retry = False   # 이번 턴에 한국어 재요청을 이미 했는가

    for iteration in range(MAX_TOOL_ITERATIONS):
        call_start = time.perf_counter()
        # 재요청 지시는 이번 호출에만 붙이고 기록에는 남기지 않는다
        extra = [KOREAN_RETRY_MESSAGE] if korean_retry else []
        response = _client.chat(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history + extra,
            tools=tools.TOOL_DEFINITIONS,
            options={"temperature": 0},
        )
        call_elapsed = time.perf_counter() - call_start
        logger.info("ollama chat call #%d took %.2fs", iteration + 1, call_elapsed)

        message = response.message

        if message.tool_calls:
            history.append(_message_to_dict(message))
            for call in message.tool_calls:
                tool_start = time.perf_counter()
                result = tools.dispatch(call.function.name, dict(call.function.arguments))
                logger.info(
                    "tool %s took %.2fs", call.function.name, time.perf_counter() - tool_start
                )
                history.append({
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False),
                })
            continue

        if message.content:
            if _HAN.search(message.content):
                logger.warning("non-Korean reply (retry=%s): %s", korean_retry, message.content[:80])
                if not korean_retry:
                    korean_retry = True
                    continue
                # 다시 요청해도 중국어면 기록에 남기지 않고 안내만 한다
                reply = NOT_KOREAN_REPLY
                break

            history.append(_message_to_dict(message))
            reply = message.content
            break

        # 도구 호출도 텍스트도 없는 빈 응답(로컬 소형 모델에서 가끔 발생) — 이 턴은
        # 히스토리에 남기지 않고 그대로 재시도한다.

    logger.info("run_agent_turn total: %.2fs", time.perf_counter() - turn_start)
    sessions.save_history(session_id, history)
    return reply

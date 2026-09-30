import json
import logging
import os
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

이동 명령의 의미:
- forward: 로봇이 현재 바라보는 방향으로 한 칸 전진
- left/right: 제자리 좌/우 회전 (좌우 평행이동이 아님)
- backward: 후진
- stop: 정지

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

    for iteration in range(MAX_TOOL_ITERATIONS):
        call_start = time.perf_counter()
        response = _client.chat(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
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
            history.append(_message_to_dict(message))
            reply = message.content
            break

        # 도구 호출도 텍스트도 없는 빈 응답(로컬 소형 모델에서 가끔 발생) — 이 턴은
        # 히스토리에 남기지 않고 그대로 재시도한다.

    logger.info("run_agent_turn total: %.2fs", time.perf_counter() - turn_start)
    sessions.save_history(session_id, history)
    return reply

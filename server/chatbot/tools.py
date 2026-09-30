import os

import requests

SERVER_BASE_URL = os.environ.get("SERVER_URL", "http://127.0.0.1:8000")

REQUEST_TIMEOUT = 10


def get_item_info(qr_code: str) -> dict:
    resp = requests.get(f"{SERVER_BASE_URL}/items/{qr_code}", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def list_items() -> dict:
    resp = requests.get(f"{SERVER_BASE_URL}/items", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return {"items": resp.json()}


def get_robot_status() -> dict:
    resp = requests.get(f"{SERVER_BASE_URL}/robot/status", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def start_delivery(qr_code: str) -> dict:
    resp = requests.get(f"{SERVER_BASE_URL}/route/{qr_code}", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def move_robot(direction: str) -> dict:
    resp = requests.post(
        f"{SERVER_BASE_URL}/test-command",
        json={"command": direction},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


TOOL_FUNCTIONS = {
    "get_item_info": get_item_info,
    "list_items": list_items,
    "get_robot_status": get_robot_status,
    "start_delivery": start_delivery,
    "move_robot": move_robot,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_item_info",
            "description": (
                "QR 코드로 물품 하나의 상태와 목적지 위치(구역 이름 zone_name, 좌표 x/y 포함)를 조회한다. "
                "물품의 QR 코드를 이미 알고 있다면(예: 'boxA') list_items 대신 반드시 이 도구를 사용할 것 — "
                "list_items는 구역 이름/좌표를 포함하지 않는다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "qr_code": {"type": "string", "description": "물품의 QR 코드 값"},
                },
                "required": ["qr_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_items",
            "description": (
                "등록된 모든 물품의 목록과 상태를 조회한다. 목적지 위치의 구역 이름(zone_name)이나 좌표는 "
                "포함되지 않고 destination_id(위치 테이블의 내부 id 번호)만 포함되므로, 이 id를 구역 이름처럼 "
                "부르거나 추측해서 답하면 안 된다. 특정 물품의 구역 이름/좌표가 필요하면 get_item_info를 사용할 것."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_robot_status",
            "description": "로봇의 현재 좌표와 상태를 조회한다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_delivery",
            "description": "QR 코드로 지정한 물품의 목적지까지 경로를 계산하고 로봇을 그 경로로 이동시킨다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "qr_code": {"type": "string", "description": "이동시킬 물품의 QR 코드 값"},
                },
                "required": ["qr_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_robot",
            "description": (
                "로봇을 한 스텝 수동으로 이동시킨다. forward=현재 바라보는 방향으로 전진, "
                "left/right=제자리 좌/우 회전, backward=후진, stop=정지."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["forward", "backward", "left", "right", "stop"],
                    },
                },
                "required": ["direction"],
            },
        },
    },
]


def dispatch(name: str, arguments: dict) -> dict:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"error": f"unknown tool: {name}"}

    try:
        return func(**arguments)
    except requests.RequestException as e:
        return {"error": f"server request failed: {e}"}
    except TypeError as e:
        return {"error": f"invalid arguments: {e}"}

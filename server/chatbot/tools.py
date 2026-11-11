import os

import requests

SERVER_BASE_URL = os.environ.get("SERVER_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("TAESULA_API_KEY", "")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

REQUEST_TIMEOUT = 10


def get_item_info(qr_code: str) -> dict:
    resp = requests.get(f"{SERVER_BASE_URL}/items/{qr_code}", timeout=REQUEST_TIMEOUT, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    destination = data.get("destination_id")
    if destination:
        destination.pop("location_id", None)
    return data


def list_items() -> dict:
    items_resp = requests.get(f"{SERVER_BASE_URL}/items", timeout=REQUEST_TIMEOUT, headers=HEADERS)
    items_resp.raise_for_status()
    items = items_resp.json()

    locations_resp = requests.get(f"{SERVER_BASE_URL}/locations", timeout=REQUEST_TIMEOUT, headers=HEADERS)
    locations_resp.raise_for_status()
    locations_by_id = {loc["id"]: loc for loc in locations_resp.json()}

    enriched = []
    for item in items:
        location = locations_by_id.get(item.get("destination_id"))
        enriched.append({
            "id": item["id"],
            "name": item["name"],
            "qr_code": item["qr_code"],
            "status": item["status"],
            "destination": {
                "zone_name": location["zone_name"],
                # "x": location["x"],
                # "y": location["y"],
            } if location else None,
        })

    return {"items": enriched}


# 작은 모델이 상태 코드를 잘못 해석하지 않도록 한국어 설명으로 풀어서 넘긴다.
ROBOT_STATE_LABEL = {
    "idle": "대기",
    "moving": "이동 중",
    "obstacle_detected": "장애물 감지로 멈춤",
}
MISSION_LABEL = {
    "deliver": "물품 배송 중",
    "return": "시작점으로 복귀 중",
}
NAV_LABEL = {
    "idle": "정상",
    "moving": "정상",
    "no_path": "장애물로 길이 막혀 자동으로 다른 길을 찾는 중",
    "manual_required": "길을 찾지 못해 사람이 장애물을 치우고 앱에서 '다시 시도'를 눌러야 함",
}


def get_robot_status() -> dict:
    # 로봇 위치·상태 + 배송/복귀 여부 + 대기열
    resp = requests.get(f"{SERVER_BASE_URL}/status", timeout=REQUEST_TIMEOUT, headers=HEADERS)
    resp.raise_for_status()
    status = resp.json()

    robot = status.get("robot_status") or {}
    queue = status.get("queue") or []
    mission = status.get("mission")

    result = {
        "position": {"x": robot.get("current_x"), "y": robot.get("current_y")},
        "robot_state": ROBOT_STATE_LABEL.get(robot.get("status"), robot.get("status")),
        "mission": MISSION_LABEL.get(mission, "진행 중인 작업 없음"),
        "current_item_qr": status.get("current_item_qr"),
        "queue": queue,
        "queue_count": len(queue),
        "queue_start_in_sec": status.get("queue_start_in_sec"),
    }

    # 장애물·재탐색 상태 (실패해도 위 정보로는 답할 수 있게)
    try:
        ob_resp = requests.get(f"{SERVER_BASE_URL}/robot/obstacles", timeout=REQUEST_TIMEOUT, headers=HEADERS)
        ob_resp.raise_for_status()
        ob = ob_resp.json()
        blocked = ob.get("blocked") or []
        result.update({
            "navigation": NAV_LABEL.get(ob.get("nav_status"), ob.get("nav_status")),
            "retry_count": ob.get("retry_count", 0),
            "blocked_cells": [
                {"x": b.get("x"), "y": b.get("y"), "marked_by_person": bool(b.get("manual"))}
                for b in blocked
            ],
            "blocked_count": len(blocked),
            "remaining_cells": len(ob.get("path") or []),
            "goal": ob.get("goal"),
        })
    except requests.RequestException:
        result["navigation"] = "장애물 정보를 가져오지 못함"

    return result

def start_delivery(qr_code: str) -> dict:
    resp = requests.get(f"{SERVER_BASE_URL}/route/{qr_code}", timeout=REQUEST_TIMEOUT, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def return_home() -> dict:
    resp = requests.post(f"{SERVER_BASE_URL}/robot/return-home", timeout=REQUEST_TIMEOUT, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


MOVE_DIRECTIONS = ("forward", "backward", "left", "right")
MOVE_MAX_STEPS = 5


def move_robot(direction: str, steps: int = 1) -> dict:
    # 배송과 같은 경로(/next-command -> robot_bridge -> ESP32)로 보내는 서버 엔드포인트를 쓴다.
    direction = str(direction).strip().lower()
    if direction not in MOVE_DIRECTIONS:
        return {
            "status": "rejected",
            "message": "방향은 forward/backward/left/right 중 하나여야 합니다. 수동 이동은 정해진 칸만큼 가고 스스로 멈춥니다.",
        }
    try:
        steps = int(steps)
    except (TypeError, ValueError):
        return {"status": "rejected", "message": "칸 수는 숫자여야 합니다."}
    if not 1 <= steps <= MOVE_MAX_STEPS:
        return {"status": "rejected", "message": f"한 번에 1~{MOVE_MAX_STEPS}칸까지만 움직일 수 있습니다."}

    resp = requests.post(
        f"{SERVER_BASE_URL}/robot/manual-move",
        json={"direction": direction, "steps": steps},
        timeout=REQUEST_TIMEOUT, headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


TOOL_FUNCTIONS = {
    "get_item_info": get_item_info,
    "list_items": list_items,
    "get_robot_status": get_robot_status,
    "start_delivery": start_delivery,
    "move_robot": move_robot,
    "return_home": return_home,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_item_info",
            "description": "등록된 모든 물품의 목록과 상태, 목적지 구역 이름(zone_name)을 조회한다.",
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
            "description": "등록된 모든 물품의 목록과 상태, 목적지 위치(구역 이름 zone_name, 좌표 x/y 포함)를 조회한다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_robot_status",
            "description": (
                "로봇의 현재 위치와 상태, 배송·복귀 중인지, 배송 중인 물품, 대기열, "
                "장애물로 막힌 칸과 경로 재탐색 상태, 목적지까지 남은 칸 수를 조회한다."
            ),
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
                "로봇을 지정한 방향으로 steps칸 평행이동시킨다(메카넘휠, 회전하지 않음). "
                "forward=앞(격자 위쪽), backward=뒤(격자 아래쪽), left=왼쪽으로 옆걸음, right=오른쪽으로 옆걸음. "
                "로봇이 쉬고 있을 때만 움직이며, 가는 칸이 벽·장애물·격자 밖이면 거절된다. "
                "결과의 status가 accepted일 때만 이동한 것이다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": list(MOVE_DIRECTIONS),
                    },
                    "steps": {
                        "type": "integer",
                        "description": f"이동할 칸 수 (1~{MOVE_MAX_STEPS}, 기본 1)",
                        "minimum": 1,
                        "maximum": MOVE_MAX_STEPS,
                    },
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "return_home",
            "description": "배송을 마친 로봇을 격자 지도의 시작점(홈)으로 복귀시킨다. 배송 중에는 거부된다.",
            "parameters": {"type": "object", "properties": {}},
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

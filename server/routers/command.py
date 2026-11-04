from fastapi import APIRouter

from server import state
from server.routers import obstacle
from server.database import get_db
from server.schemas.request_models import (
    CommandDoneRequest,
    CommandRequest,
    PathRequest,
    TestCommandRequest,
)


router = APIRouter()

test_command = "stop"
test_command_ready = False


@router.get("/command")
def get_command():
    return {"direction": state.current_command}


# 횡이동(메카넘휠) 기준: 로봇은 항상 격자 북쪽을 바라본다.
# 명령 1칸당 좌표 변화량 (x: 오른쪽 +, y: 아래쪽 +)
MOVE_DELTA = {
    "forward": (0, -1),
    "backward": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


def has_move_command(path):
    return any(command in MOVE_DELTA for command in path)


@router.get("/next-command")
def get_next_command():
    obstacle.commit_pending_move()

    if not state.current_path:
        state.current_command = "stop"
        state.current_steps = 0

        return {
            "direction": "stop",
            "steps": 0,
            "message": "path is empty",
            "remaining_path": state.current_path
        }

    # 같은 이동 명령이 연달아 있으면 묶어서 한 번에 보낸다.
    # 예: forward, forward, forward -> {"direction": "forward", "steps": 3}
    command = state.current_path.pop(0)
    steps = 1

    if command in MOVE_DELTA:
        while state.current_path and state.current_path[0] == command:
            state.current_path.pop(0)
            steps += 1
    else:
        steps = 0

    state.current_command = command
    state.current_steps = steps

    extras = obstacle.mark_dispatched(command, steps)

    return {
        "direction": command,
        "steps": steps,
        "remaining_path": state.current_path
        **extras
    }


@router.post("/command/done")
def command_done(report: CommandDoneRequest):
    conn = get_db()
    cursor = conn.cursor()

    # 1. 실제로 이동한 칸 수만큼 로봇 위치 갱신
    dx, dy = MOVE_DELTA.get(report.command, (0, 0))
    moved = report.steps if report.command in MOVE_DELTA else 0

    if moved:
        cursor.execute(
            """
            UPDATE robot_status
            SET current_x = current_x + ?, current_y = current_y + ?
            WHERE id = 1
            """,
            (dx * moved, dy * moved)
        )

    arrived = False

    # 2. 장애물로 멈춘 경우: 못 간 칸은 경로 앞에 되돌려 놓고 상태만 변경
    if report.result == "obstacle":
        not_moved = max(state.current_steps - moved, 0)

        if report.command in MOVE_DELTA and not_moved:
            state.current_path[0:0] = [report.command] * not_moved

        cursor.execute(
            "UPDATE robot_status SET status = 'obstacle_detected' WHERE id = 1"
        )

    # 3. 남은 이동 명령이 없으면 배송 완료
    elif not has_move_command(state.current_path):
        cursor.execute("UPDATE robot_status SET status = 'idle' WHERE id = 1")

        if state.current_item_qr:
            cursor.execute(
                "UPDATE items SET status = 'arrived' WHERE qr_code = ?",
                (state.current_item_qr,)
            )
            arrived = True

        state.current_item_qr = None

    # 4. 아직 갈 길이 남았으면 이동 중
    else:
        cursor.execute("UPDATE robot_status SET status = 'moving' WHERE id = 1")

    state.current_steps = 0

    cursor.execute(
        "SELECT current_x, current_y, status FROM robot_status WHERE id = 1"
    )
    row = cursor.fetchone()

    conn.commit()
    conn.close()

    return {
        "message": "command done reported",
        "current_x": row[0] if row else None,
        "current_y": row[1] if row else None,
        "status": row[2] if row else None,
        "arrived": arrived,
        "remaining_path": state.current_path
    }


@router.post("/command")
def set_command(command: CommandRequest):
    state.current_command = command.direction

    return {
        "message": "command updated",
        "direction": state.current_command
    }


@router.post("/path")
def set_path(path_data: PathRequest):
    state.current_path = path_data.path

    return {
        "message": "path updated",
        "path": state.current_path
    }


@router.post("/test-command")
def set_test_command(request: TestCommandRequest):
    global test_command, test_command_ready

    test_command = request.command
    test_command_ready = True

    return {
        "message": "test command set",
        "command": test_command,
        "ready": test_command_ready
    }


@router.get("/test-command")
def get_test_command():
    global test_command, test_command_ready

    if not test_command_ready:
        return {
            "direction": "stop",
            "source": "test-command",
            "message": "no test command"
        }

    command_to_send = test_command

    # ESP32가 한 번 받아가면 다시 stop 상태로 초기화
    test_command = "stop"
    test_command_ready = False

    return {
        "direction": command_to_send,
        "source": "test-command",
        "message": "test command consumed"
    }

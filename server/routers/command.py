from fastapi import APIRouter

from server import state
from server.schemas.request_models import (
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


@router.get("/next-command")
def get_next_command():
    if not state.current_path:
        state.current_command = "stop"

        return {
            "direction": "stop",
            "message": "path is empty",
            "remaining_path": state.current_path
        }

    state.current_command = state.current_path.pop(0)

    return {
        "direction": state.current_command,
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

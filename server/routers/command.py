from fastapi import APIRouter

from server.schemas.request_models import CommandRequest, PathRequest


router = APIRouter()

current_command = "stop"
current_path = []


@router.get("/command")
def get_command():
    return {"direction": current_command}


@router.get("/next-command")
def get_next_command():
    global current_command, current_path

    if not current_path:
        current_command = "stop"
        return {
            "direction": "stop",
            "message": "path is empty",
            "remaining_path": current_path
        }

    current_command = current_path.pop(0)

    return {
        "direction": current_command,
        "remaining_path": current_path
    }


@router.post("/command")
def set_command(command: CommandRequest):
    global current_command

    current_command = command.direction

    return {
        "message": "command updated",
        "direction": current_command
    }


@router.post("/path")
def set_path(path_data: PathRequest):
    global current_path

    current_path = path_data.path

    return {
        "message": "path updated",
        "path": current_path
    }

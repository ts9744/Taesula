
from fastapi import APIRouter
from server.schemas import CommandRequest, PathRequest, StatusRequest, Direction, RobotStatus

router = APIRouter(
    prefix="/robot",
    tags=["Robot"]
)
robot_status: RobotStatus = "idle"
current_command: Direction = "stop"
current_path: list[Direction] = []


@router.get("/status")
def get_status():
    return {
        "robot_status": robot_status,
        "current_command": current_command,
        "current_path": current_path
    }


@router.post("/status")
def update_status(status_data: StatusRequest):
    global robot_status

    robot_status = status_data.robot_status

    return {
        "message": "status updated",
        "robot_status": robot_status
    }


@router.get("/command")
def get_command():
    return {"direction": current_command}


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
@router.get("/command")
def get_command():
    return {"direction": current_command}


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
cat > server/api/robot.py <<'EOF'

from fastapi import APIRouter
from server.schemas import CommandRequest, PathRequest, StatusRequest, Direction, RobotStatus

router = APIRouter(
    prefix="/robot",
    tags=["Robot"]
)
robot_status: RobotStatus = "idle"
current_command: Direction = "stop"
current_path: list[Direction] = []


@router.get("/status")
def get_status():
    return {
        "robot_status": robot_status,
        "current_command": current_command,
        "current_path": current_path
    }


@router.post("/status")
def update_status(status_data: StatusRequest):
    global robot_status

    robot_status = status_data.robot_status

    return {
        "message": "status updated",
        "robot_status": robot_status
    }


@router.get("/command")
def get_command():
    return {"direction": current_command}


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
@router.get("/command")
def get_command():
    return {"direction": current_command}


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
        "remaining_path": current_pat

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

robot_status = "idle"
current_command = "stop"
current_path = []


class CommandRequest(BaseModel):
    direction: str

class PathRequest(BaseModel):
    path: list[str]

@app.get("/")
def root():
    return {"message": "robot communication server is running"}

@app.get("/status")
def get_status():
    return {
        "robot_status": robot_status,
        "current_command": current_command,
        "current_path": current_path
    }

@app.get("/command")
def get_command():
    return {"direction": current_command}

@app.post("/command")
def set_command(command: CommandRequest):
    global current_command

    current_command = command.direction

    return {
        "message": "command updated",
        "direction": current_command
    }

@app.post("/path")
def set_path(path_data: PathRequest):
    global current_path

    current_path = path_data.path

    return {
        "message": "path updated",
        "path": current_path
    }
from typing import Literal

from pydantic import BaseModel
from pydantic import BaseModel, Field


Direction = Literal["forward", "backward", "left", "right", "stop"]
RobotStatus = Literal["idle", "moving", "stopped", "obstacle_detected", "error"]


class CommandRequest(BaseModel):
    direction: Direction


class PathRequest(BaseModel):
    path: list[Direction]


class CommandDoneRequest(BaseModel):
    # 로봇(ESP32)이 명령 실행을 마친 뒤 보내는 보고
    command: Direction
    steps: int = Field(default=1, ge=0)                # 실제로 이동한 칸 수
    result: Literal["done", "obstacle"] = "done"       # 정상 완료 / 장애물로 정지


class GridMapRequest(BaseModel):
    rows: int
    cols: int
    raw_grid: list[list[int]]
    pathfinding_grid: list[list[int]]


class StatusRequest(BaseModel):
    robot_status: RobotStatus
    
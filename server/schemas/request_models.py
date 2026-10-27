from typing import Literal

from pydantic import BaseModel


Direction = Literal["forward", "backward", "left", "right", "stop"]
RobotStatus = Literal["idle", "moving", "stopped", "obstacle_detected", "error"]


class CommandRequest(BaseModel):
    direction: Direction


class PathRequest(BaseModel):
    path: list[Direction]


class TestCommandRequest(BaseModel):
    command: Direction


class GridMapRequest(BaseModel):
    rows: int
    cols: int
    raw_grid: list[list[int]]
    pathfinding_grid: list[list[int]]


class StatusRequest(BaseModel):
    robot_status: RobotStatus
    
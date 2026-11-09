import os
import threading
import time

import requests
import serial

API = "http://127.0.0.1:8000"
API_KEY = os.environ.get("TAESULA_API_KEY", "")
PORT = os.environ.get(
    "TAESULA_ESP32_PORT",
    "/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0",
)
BAUD = 115200
STEP_SEC = 1.5          # 1칸 이동 + 여유 (FORWARD_RUN_MS = 1000)
IDLE_POLL_SEC = 1.0
RECONNECT_SEC = 2.0
HEARTBEAT_SEC = 2.0

MSG_NOT_CONNECTED = "ESP32가 연결되어 있지 않습니다. 라즈베리파이 USB에 ESP32를 연결해 주세요."

HEADERS = {"X-API-Key": API_KEY}

# 서버에 주기적으로 보고할 연결 상태 (heartbeat 스레드가 읽음)
link = {"connected": False, "message": MSG_NOT_CONNECTED}


class SerialLost(Exception):
    pass

class Resume(Exception):
    """halt 후 '시작점에 놓기'가 확인되어 다시 시작한다."""
    pass

def api_get(path):
    r = requests.get(f"{API}{path}", headers=HEADERS, timeout=5)
    r.raise_for_status()
    return r.json()


def api_post(path, body):
    r = requests.post(f"{API}{path}", json=body, headers=HEADERS, timeout=5)
    r.raise_for_status()
    return r.json()

CELL_CM = 34.0
FORWARD_RUN_MS = 1000


def report_obstacle(reply):
    """ESP32 'OBSTACLE <방향> <끝낸 칸 수> <움직인 ms> <거리cm>' -> 서버 보고"""
    try:
        _, direction, cells_done, ran_ms, dist = reply.split()
        cells_done = int(cells_done)
        moved_cm = (cells_done + int(ran_ms) / FORWARD_RUN_MS) * CELL_CM
        api_post("/robot/obstacle", {
            "direction": direction,
            "distance_cm": float(dist),
            "moved_cm": moved_cm,
            "completed": False,
            "cells_done": cells_done,
        })
        print("obstacle reported:", reply)
        return True
    except (ValueError, requests.RequestException) as e:
        print("obstacle report error:", e)
        return False


def set_link(connected, message=""):
    if link["connected"] != connected or link["message"] != message:
        print(f"[link] connected={connected} {message}")
    link["message"] = message
    link["connected"] = connected


def heartbeat_loop():
    """연결 상태를 서버에 계속 알린다. 브리지가 죽으면 보고가 끊겨 서버가 알아챈다."""
    while True:
        try:
            requests.post(
                f"{API}/robot/esp32",
                json={"connected": link["connected"], "message": link["message"]},
                headers=HEADERS,
                timeout=3,
            )
        except requests.RequestException:
            pass
        time.sleep(HEARTBEAT_SEC)


def flush_esp32(ser):
    """ESP32 쪽에 남은 미완성 줄을 끊고, 라즈베리파이 쪽 수신 버퍼도 비운다."""
    ser.write(b"\n")
    time.sleep(0.2)
    ser.reset_input_buffer()


def send_and_wait(ser, line, expect, timeout):
    """line을 보내고 expect와 정확히 같은 응답을 기다린다.
    반환: "ok" / "err" / "timeout"
    연결이 끊기면 SerialLost 발생
    """
    try:
        ser.reset_input_buffer()
        ser.write((line + "\n").encode())

        end = time.time() + timeout
        while time.time() < end:
            check_link(ser)                 # 추가
            reply = ser.readline().decode(errors="ignore").strip()
            if not reply:
                continue
            print("ESP32:", reply)
            if reply == expect:
                return "ok"
            if reply.startswith("OBSTACLE"):
                return reply
            if reply.startswith("ERR"):
                return "err"
            if reply == "READY":
                return "reset"   # 이동 중 ESP32 재부팅(브라운아웃 등)
            # 그 외(READY, 이전 명령의 늦은 DONE 등)는 무시
        return "timeout"
    except (serial.SerialException, OSError) as e:
        raise SerialLost(str(e))

def wait_for_placement(halted_at):
    """앱에서 '시작점에 놓기'를 할 때까지 기다린다. (서버와 브리지가 같은 Pi라 시각 비교가 가능)"""
    while True:
        time.sleep(2)
        try:
            st = api_get("/status")
        except requests.RequestException:
            continue
        if st.get("placed_at", 0) > halted_at:
            return

def check_link(ser):
    """USB가 빠졌거나(링크 사라짐), 빠졌다 다시 꽂혀 다른 장치(ttyUSB1 등)가 됐으면 SerialLost.
    pyserial은 USB가 빠져도 예외 없이 빈 응답만 줄 수 있어서 직접 확인한다."""
    if not os.path.exists(PORT) or os.path.realpath(PORT) != getattr(ser, "dev", None):
        raise SerialLost("USB 연결 끊김 또는 재연결됨")

def halt(ser, reason):
    """로봇을 세우고, 사람이 위치를 맞출 때까지 기다린 뒤 다시 시작한다."""
    halted_at = time.time()
    if ser is not None:
        try:
            send_and_wait(ser, "stop", "DONE stop 0", 3)
        except SerialLost:
            pass
        try:
            ser.close()
        except Exception:
            pass
    msg = f"로봇이 정지되었습니다({reason}). 로봇을 시작점에 놓고 '시작점에 놓기'를 누르면 다시 시작합니다."
    set_link(False, msg)
    print("HALT:", reason)

    wait_for_placement(halted_at)
    print("RESUME: 시작점 재배치 확인, 다시 연결합니다")
    raise Resume()


def open_esp32():
    """ESP32가 꽂힐 때까지 기다렸다가 포트를 연다."""
    while True:
        if not os.path.exists(PORT):
            set_link(False, MSG_NOT_CONNECTED)
            time.sleep(RECONNECT_SEC)
            continue
        try:
            ser = serial.Serial(PORT, BAUD, timeout=0.5)
            ser.dev = os.path.realpath(PORT)      # 열었을 때의 실제 장치(ttyUSB0 등)
            time.sleep(2)               # 포트 열 때 ESP32 리셋 대기
            flush_esp32(ser)
            return ser
        except (serial.SerialException, OSError) as e:
            set_link(False, MSG_NOT_CONNECTED)
            print("open failed:", e)
            time.sleep(RECONNECT_SEC)


def run(ser):
    while True:
        # 명령을 꺼내기 전에 연결부터 확인 (꺼낸 뒤 끊기면 그 명령이 사라진다)
        check_link(ser)                 # 기존: if not os.path.exists(PORT): raise SerialLost(...)
        if not os.path.exists(PORT):
            raise SerialLost("port removed")

        try:
            cmd = api_get("/next-command")
        except requests.RequestException as e:
            print("server error:", e)
            time.sleep(2)
            continue

        direction = cmd.get("direction")
        steps = cmd.get("steps", 0)

        if direction is None:
            print("unexpected response:", cmd)
            time.sleep(2)
            continue

        # 경로가 비어 있음: 대기
        if direction == "stop" and cmd.get("message") == "path is empty":
            time.sleep(IDLE_POLL_SEC)
            continue

        # 경로 끝의 stop: 정지 후 도착 처리
        if direction == "stop":
            try:
                result = send_and_wait(ser, "stop", "DONE stop 0", 3)
            except SerialLost:
                halt(None, "도착 stop 전송 중 ESP32 연결 끊김")
            if result != "ok":
                halt(ser, f"도착 stop 실패 ({result})")
            try:
                api_post("/command/done", {"command": "stop", "steps": 0, "result": "done"})
                print("arrived")
            except requests.RequestException as e:
                print("done report error:", e)
            continue

        line = f"{direction} {steps}"
        expect = f"DONE {direction} {steps}"
        timeout = steps * STEP_SEC + 5
        print("send:", line)

        try:
            result = send_and_wait(ser, line, expect, timeout)

            # ERR: ESP32가 명령을 거부한 것이라 로봇은 움직이지 않았다 -> 한 번 재시도
            if result == "err":
                print("ERR, retry once")
                flush_esp32(ser)
                result = send_and_wait(ser, line, expect, timeout)
        except SerialLost:
            # 이동 도중 끊김: 실제로 몇 칸 갔는지 알 수 없다
            halt(None, f"'{line}' 이동 중 ESP32 연결 끊김")

        if result.startswith("OBSTACLE"):
            if not report_obstacle(result):
                halt(ser, f"장애물 보고 실패 ({result})")
            continue
        if result != "ok":
            # 다음 /next-command 를 부르면 commit_pending_move()가
            # 이 이동을 완료로 처리하므로, 여기서 멈춰야 위치가 어긋나지 않는다.
            halt(ser, f"'{line}' 실패 ({result})")

        # ok면 다음 /next-command 호출 -> commit_pending_move()가 위치 갱신


def main():
    if not API_KEY:
        print("TAESULA_API_KEY not set")
        return

    threading.Thread(target=heartbeat_loop, daemon=True).start()
    print("bridge started")

    while True:
        ser = open_esp32()
        set_link(True, "")
        try:
            run(ser)
        except (SerialLost, Resume) as e:
            print("ESP32 disconnected:", e)
            set_link(False, MSG_NOT_CONNECTED)
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(RECONNECT_SEC)


if __name__ == "__main__":
    main()
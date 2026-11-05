import os
import time

import requests
import serial

API = "http://127.0.0.1:8000"
API_KEY = os.environ.get("TAESULA_API_KEY", "")
PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0"
BAUD = 115200
STEP_SEC = 1.5      # 1칸 이동 + 여유 (FORWARD_RUN_MS = 1000)
IDLE_POLL_SEC = 1.0

http = requests.Session()
http.headers["X-API-Key"] = API_KEY


def api_get(path):
    r = http.get(f"{API}{path}", timeout=5)
    r.raise_for_status()
    return r.json()


def api_post(path, body):
    r = http.post(f"{API}{path}", json=body, timeout=5)
    r.raise_for_status()
    return r.json()


def flush_esp32(ser):
    """ESP32 쪽에 남은 미완성 줄을 끊고, 라즈베리파이 쪽 수신 버퍼도 비운다."""
    ser.write(b"\n")
    time.sleep(0.2)
    ser.reset_input_buffer()


def send_and_wait(ser, line, expect, timeout):
    """line을 보내고 expect와 정확히 같은 응답을 기다린다.
    반환: "ok" / "err" / "timeout"
    """
    ser.reset_input_buffer()
    ser.write((line + "\n").encode())

    end = time.time() + timeout
    while time.time() < end:
        reply = ser.readline().decode(errors="ignore").strip()
        if not reply:
            continue
        print("ESP32:", reply)
        if reply == expect:
            return "ok"
        if reply.startswith("ERR"):
            return "err"
        # 그 외(READY, 이전 명령의 늦은 DONE 등)는 무시
    return "timeout"


def halt(ser, reason):
    """로봇을 세우고 브리지를 멈춘다. 위치가 어긋났을 수 있으므로 수동 확인 필요."""
    send_and_wait(ser, "stop", "DONE stop 0", 3)
    print(f"HALT: {reason}")
    print("로봇 실제 위치 확인 후 PUT /robot/status 로 DB 위치를 맞추고 브리지를 다시 실행하세요.")
    while True:
        time.sleep(60)


def main():
    if not API_KEY:
        print("TAESULA_API_KEY not set")
        return

    ser = serial.Serial(PORT, BAUD, timeout=0.5)
    time.sleep(2)               # 포트 열 때 ESP32 리셋 대기
    flush_esp32(ser)
    print("bridge started")

    while True:
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
            send_and_wait(ser, "stop", "DONE stop 0", 3)
            try:
                api_post(
                    "/command/done",
                    {"command": "stop", "steps": 0, "result": "done"},
                )
                print("arrived")
            except requests.RequestException as e:
                print("done report error:", e)
            continue

        line = f"{direction} {steps}"
        expect = f"DONE {direction} {steps}"
        timeout = steps * STEP_SEC + 5
        print("send:", line)

        result = send_and_wait(ser, line, expect, timeout)

        # ERR: ESP32가 명령을 거부한 것이라 로봇은 움직이지 않았다 -> 한 번 재시도
        if result == "err":
            print("ERR, retry once")
            flush_esp32(ser)
            result = send_and_wait(ser, line, expect, timeout)

        if result != "ok":
            # 다음 /next-command 를 부르면 commit_pending_move()가
            # 이 이동을 완료로 처리하므로, 여기서 멈춰야 위치가 어긋나지 않는다.
            halt(ser, f"'{line}' 실패 ({result})")

        # ok면 다음 /next-command 호출 -> commit_pending_move()가 위치 갱신


if __name__ == "__main__":
    main()
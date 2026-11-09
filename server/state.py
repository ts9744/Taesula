current_command = "stop"
current_path = []

# 배송 진행 상황 추적용
current_item_qr = None   # 지금 배송 중인 물품의 QR 코드 (/route에서 설정)
current_steps = 0        # 마지막으로 /next-command에서 보낸 칸 수
goal = None
pending_move = None
skip_detect = False

# 복귀 관련
mission = None          # "deliver"(배송 중) / "return"(홈 복귀 중) / None
return_at = None        # 자동 복귀 예약 시각 (time.time() 기준)


placed_at = 0.0   # 마지막으로 '시작점에 놓기'를 한 시각 (브리지 halt 해제 신호)
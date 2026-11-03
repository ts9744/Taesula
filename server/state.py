current_command = "stop"
current_path = []

# 배송 진행 상황 추적용
current_item_qr = None   # 지금 배송 중인 물품의 QR 코드 (/route에서 설정)
current_steps = 0        # 마지막으로 /next-command에서 보낸 칸 수

"""관리자만 할 수 있는 작업(격자 지도 저장, 목적지 추가/수정/삭제)을 막는다.

시연 때 관객도 앱을 쓰므로, 지도를 바꾸는 요청은 X-Admin-Key 헤더에 관리자 키가 있어야 받는다.
API 키(X-API-Key, 외부 접속용)와 별개이고, 같은 Wi-Fi 에서 온 요청도 검사한다.
TAESULA_ADMIN_KEY 를 설정하지 않으면 검사하지 않는다 (개발용).
"""
import os
import secrets

from fastapi import APIRouter, Header, HTTPException

ADMIN_KEY = os.environ.get("TAESULA_ADMIN_KEY", "")

router = APIRouter()


def is_admin(key: str) -> bool:
    if not ADMIN_KEY:
        return True
    return bool(key) and secrets.compare_digest(key.encode("utf-8"), ADMIN_KEY.encode("utf-8"))


def require_admin(x_admin_key: str = Header(default="")):
    """관리자 전용 엔드포인트에 dependencies=[Depends(require_admin)] 로 붙인다."""
    if not is_admin(x_admin_key):
        raise HTTPException(status_code=403, detail="관리자만 할 수 있는 작업입니다.")


@router.get("/admin/check")
def admin_check(x_admin_key: str = Header(default="")):
    """앱이 편집 버튼을 보여줄지 정할 때 쓴다. enabled=False 면 관리자 키 없이 누구나 편집할 수 있다."""
    return {"enabled": bool(ADMIN_KEY), "admin": is_admin(x_admin_key)}

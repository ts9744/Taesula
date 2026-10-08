"""
모바일 앱(mobile/ 폴더)을 FastAPI 서버에서 함께 제공하기 위한 설정.

server.py에서 app을 만든 뒤 한 줄만 추가하면 됩니다.

    from mobile_app import setup_mobile
    setup_mobile(app, BASE_DIR)

그러면 휴대폰 브라우저에서 http://<라즈베리파이 IP>:8000/app/ 으로 앱을 열 수 있습니다.
앱과 API가 같은 주소에서 나오므로 CORS 설정이 따로 필요 없습니다.
"""

import io
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles


def setup_mobile(app: FastAPI, base_dir: Path) -> None:
    mobile_dir = Path(base_dir) / "mobile"

    @app.get("/mobile-api/qr.png", tags=["mobile"])
    def qr_png(text: str = Query(..., min_length=1, max_length=500)):
        """QR 코드 PNG를 만든다. (데스크톱 GUI의 물품 등록과 같은 qrcode 패키지 사용)"""
        try:
            import qrcode
        except ImportError:
            raise HTTPException(status_code=500, detail="서버에 qrcode 패키지가 설치되어 있지 않습니다.")

        qr = qrcode.QRCode(border=2, box_size=10)
        qr.add_data(text)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return Response(
            content=buffer.getvalue(),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    if not mobile_dir.is_dir():
        print(f"[mobile] {mobile_dir} 폴더가 없어 모바일 앱을 제공하지 않습니다.")
        return

    @app.get("/app", include_in_schema=False)
    def mobile_root():
        return RedirectResponse(url="/app/")

    app.mount("/app", StaticFiles(directory=mobile_dir, html=True), name="mobile")

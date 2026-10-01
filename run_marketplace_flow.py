"""Run with: uvicorn run_marketplace_flow:app --reload"""

from marketplace_otp.order_handoff_service import create_app

app = create_app()

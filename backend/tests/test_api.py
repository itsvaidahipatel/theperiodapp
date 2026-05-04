import pytest
from httpx import AsyncClient
from main import app # This imports your FastAPI app

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/health") # Change to your actual health or root path
    assert response.status_code == 200
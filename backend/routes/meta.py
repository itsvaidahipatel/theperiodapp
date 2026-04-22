from fastapi import APIRouter

router = APIRouter()


@router.get("/social-links")
def get_social_links():
    # Response intentionally list-based so clients can render any number of platforms.
    return [
        {
            "name": "Instagram",
            "url": "https://instagram.com",
            "platform_key": "instagram",
        },
        {
            "name": "Youtube",
            "url": "https://youtube.com",
            "platform_key": "youtube",
        },
        {
            "name": "Mail",
            "url": "mailto:support@periodcycle.ai",
            "platform_key": "mail",
        },
    ]

from supabase import create_client, Client
import config

supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

async def add_or_update_user(telegram_id: int, username: str, pocket_id: str):
    """Добавление или обновление данных пользователя в Supabase."""
    data = {
        "telegram_id": telegram_id,
        "username": username,
        "pocket_id": pocket_id,
        "approved": False
    }
    # upsert обновит запись, если telegram_id уже есть, или создаст новую
    supabase.table("users").upsert(data, on_conflict="telegram_id").execute()

async def set_approve_status(telegram_id: int, status: bool):
    """Смена статуса доступа (approved = True / False)."""
    supabase.table("users").update({"approved": status}).eq("telegram_id", telegram_id).execute()

async def is_user_approved(telegram_id: int) -> bool:
    """Проверка наличия доступа у пользователя."""
    response = supabase.table("users").select("approved").eq("telegram_id", telegram_id).execute()
    if response.data:
        return response.data[0].get("approved", False)
    return False

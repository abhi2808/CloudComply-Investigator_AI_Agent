from bson import ObjectId
from datetime import datetime, timezone
from app.db.mongodb import get_database

class AccountRepository:
    async def add_account(self, user_id: str, nickname: str, region: str,
                          encrypted_access_key: str, encrypted_secret_key: str) -> dict:
        db = get_database()
        doc = {
            "user_id": ObjectId(user_id),
            "nickname": nickname,
            "region": region,
            "access_key_id": encrypted_access_key,
            "secret_access_key": encrypted_secret_key,
            "created_at": datetime.now(timezone.utc),
            "last_verified": None,
            "is_active": True
        }
        result = await db.accounts.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def get_accounts_by_user(self, user_id: str) -> list[dict]:
        db = get_database()
        cursor = db.accounts.find({"user_id": ObjectId(user_id)}, {
            "access_key_id": 0,
            "secret_access_key": 0
        })
        return await cursor.to_list(length=None)

    async def get_account_by_id(self, account_id: str, user_id: str) -> dict | None:
        db = get_database()
        try:
            return await db.accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": ObjectId(user_id)
            })
        except Exception:
            return None

    async def get_account_for_bot(self, account_id: str) -> dict | None:
        """
        Fetch an account by _id only, without checking user_id ownership.
        Used exclusively by the Teams bot where all users share one PoC account.
        """
        db = get_database()
        try:
            return await db.accounts.find_one({"_id": ObjectId(account_id)})
        except Exception:
            return None

    async def delete_account(self, account_id: str, user_id: str) -> bool:
        db = get_database()
        try:
            result = await db.accounts.delete_one({
                "_id": ObjectId(account_id),
                "user_id": ObjectId(user_id)
            })
            return result.deleted_count > 0
        except Exception:
            return False

    async def update_last_verified(self, account_id: str) -> None:
        db = get_database()
        try:
            await db.accounts.update_one(
                {"_id": ObjectId(account_id)},
                {"$set": {"last_verified": datetime.now(timezone.utc)}}
            )
        except Exception:
            pass

account_repository = AccountRepository()

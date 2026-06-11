import os
import sys
import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Reconfigure stdout/stderr to handle UTF-8 Persian characters in Windows console
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass  # In case stdout doesn't support reconfigure (e.g. in some IDE test runners)

# Set environment variable before imports to ensure it is picked up
os.environ["DATABASE_URL"] = "sqlite:///./test_haftyar.db"
os.environ["ENV"] = "dev"

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.services import message_service

# Create database engine and session for test database
TEST_DB_URL = "sqlite:///./test_haftyar.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Mock list to collect sent replies
SENT_REPLIES = []

# Override send_bot_reply to capture instead of sending network request
async def mock_send_bot_reply(platform: str, chat_id: str, text: str, reply_markup: dict | None = None) -> bool:
    try:
        print(f"\n[BOT REPLY - Platform: {platform}, Chat ID: {chat_id}]")
        print(f"Content:\n{text}")
        if reply_markup:
            print(f"Markup: {reply_markup}")
        print("-" * 50)
    except Exception:
        # Fallback in case encoding still fails somewhere
        pass
    SENT_REPLIES.append({
        "platform": platform,
        "chat_id": chat_id,
        "text": text,
        "reply_markup": reply_markup
    })
    return True

# Apply the mock
message_service.send_bot_reply = mock_send_bot_reply


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


class TestWebhookBotCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Clean up existing test database if exists
        if os.path.exists("./test_haftyar.db"):
            try:
                os.remove("./test_haftyar.db")
            except Exception:
                pass
        # Initialize tables
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        # Dispose the engine to close all connections
        engine.dispose()
        # Clean up database after test
        if os.path.exists("./test_haftyar.db"):
            try:
                os.remove("./test_haftyar.db")
            except Exception:
                pass

    def setUp(self):
        SENT_REPLIES.clear()

    def test_complete_webhook_flow(self):
        print("\n=== STARTING COMPLETE WEBHOOK BOT FLOW TEST ===")

        # 1. Message from an unlinked user (should request contact)
        payload_start = {
            "message": {
                "message_id": 1001,
                "from": {"id": 111111, "first_name": "Ali", "username": "ali_test"},
                "chat": {"id": 111111, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "text": "/start"
            }
        }
        response = self.client.post("/api/v1/webhooks/telegram", json=payload_start)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "accepted")
        
        # Verify bot asked for contact sharing
        self.assertEqual(len(SENT_REPLIES), 1)
        self.assertIn("نیاز به احراز شماره موبایل شما داریم", SENT_REPLIES[0]["text"])
        self.assertTrue(SENT_REPLIES[0]["reply_markup"]["keyboard"][0][0]["request_contact"])

        # 2. User shares contact (should register and link account)
        SENT_REPLIES.clear()
        payload_contact = {
            "message": {
                "message_id": 1002,
                "from": {"id": 111111, "first_name": "Ali", "username": "ali_test"},
                "chat": {"id": 111111, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "contact": {
                    "phone_number": "09121111111",
                    "first_name": "Ali",
                    "user_id": 111111
                }
            }
        }
        response = self.client.post("/api/v1/webhooks/telegram", json=payload_contact)
        self.assertEqual(response.status_code, 200)
        self.assertIn("ثبت‌نام شما در هفته‌یار با موفقیت انجام شد", SENT_REPLIES[0]["text"])

        # 3. Linked user requests help
        SENT_REPLIES.clear()
        payload_help = {
            "message": {
                "message_id": 1003,
                "from": {"id": 111111, "first_name": "Ali", "username": "ali_test"},
                "chat": {"id": 111111, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "text": "/help"
            }
        }
        response = self.client.post("/api/v1/webhooks/telegram", json=payload_help)
        self.assertEqual(response.status_code, 200)
        self.assertIn("لیست دستورات فعال ربات", SENT_REPLIES[0]["text"])

        # 4. Create a new team
        SENT_REPLIES.clear()
        payload_create_team = {
            "message": {
                "message_id": 1004,
                "from": {"id": 111111, "first_name": "Ali", "username": "ali_test"},
                "chat": {"id": 111111, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "text": "/create_team تیم تستی علی"
            }
        }
        response = self.client.post("/api/v1/webhooks/telegram", json=payload_create_team)
        self.assertEqual(response.status_code, 200)
        self.assertIn("با موفقیت ساخته شد", SENT_REPLIES[0]["text"])
        
        # Extract team ID from response text
        # Content format: "... شناسه تیم: `team_uuid` ..."
        text = SENT_REPLIES[0]["text"]
        team_id = text.split("شناسه تیم: `")[1].split("`")[0]
        print(f"--> Extracted Team ID: {team_id}")

        # 5. List teams
        SENT_REPLIES.clear()
        payload_teams = {
            "message": {
                "message_id": 1005,
                "from": {"id": 111111, "first_name": "Ali", "username": "ali_test"},
                "chat": {"id": 111111, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "text": "/teams"
            }
        }
        response = self.client.post("/api/v1/webhooks/telegram", json=payload_teams)
        self.assertEqual(response.status_code, 200)
        self.assertIn("تیم تستی علی", SENT_REPLIES[0]["text"])
        self.assertIn(team_id, SENT_REPLIES[0]["text"])

        # 6. Invite another user (Reza) using phone number
        SENT_REPLIES.clear()
        payload_invite = {
            "message": {
                "message_id": 1006,
                "from": {"id": 111111, "first_name": "Ali", "username": "ali_test"},
                "chat": {"id": 111111, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "text": f"/invite {team_id} 09122222222"
            }
        }
        response = self.client.post("/api/v1/webhooks/telegram", json=payload_invite)
        self.assertEqual(response.status_code, 200)
        self.assertIn("با موفقیت به تیم دعوت و عضو شد", SENT_REPLIES[0]["text"])

        # 7. Check members list
        SENT_REPLIES.clear()
        payload_members = {
            "message": {
                "message_id": 1007,
                "from": {"id": 111111, "first_name": "Ali", "username": "ali_test"},
                "chat": {"id": 111111, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "text": f"/members {team_id}"
            }
        }
        response = self.client.post("/api/v1/webhooks/telegram", json=payload_members)
        self.assertEqual(response.status_code, 200)
        self.assertIn("09122222222", SENT_REPLIES[0]["text"])
        self.assertIn("09121111111", SENT_REPLIES[0]["text"])

        # 8. Create a task assigned to Reza (09122222222)
        SENT_REPLIES.clear()
        payload_create_task = {
            "message": {
                "message_id": 1008,
                "from": {"id": 111111, "first_name": "Ali", "username": "ali_test"},
                "chat": {"id": 111111, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "text": f"/create_task {team_id} طراحی لوگوی هفته‌یار @09122222222 این تسک بسیار فوری است"
            }
        }
        response = self.client.post("/api/v1/webhooks/telegram", json=payload_create_task)
        self.assertEqual(response.status_code, 200)
        self.assertIn("تسک با موفقیت ایجاد شد", SENT_REPLIES[0]["text"])
        self.assertIn("طراحی لوگوی هفته‌یار", SENT_REPLIES[0]["text"])
        
        # Extract task ID
        text = SENT_REPLIES[0]["text"]
        task_id = text.split("شناسه تسک: `")[1].split("`")[0]
        print(f"--> Extracted Task ID: {task_id}")

        # 9. Register/link Reza (the assignee) to verify they can see and update the task
        # Reza starts the bot
        SENT_REPLIES.clear()
        payload_reza_start = {
            "message": {
                "message_id": 2001,
                "from": {"id": 222222, "first_name": "Reza", "username": "reza_test"},
                "chat": {"id": 222222, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "text": "/start"
            }
        }
        self.client.post("/api/v1/webhooks/telegram", json=payload_reza_start)
        
        # Reza shares contact
        SENT_REPLIES.clear()
        payload_reza_contact = {
            "message": {
                "message_id": 2002,
                "from": {"id": 222222, "first_name": "Reza", "username": "reza_test"},
                "chat": {"id": 222222, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "contact": {
                    "phone_number": "09122222222",
                    "first_name": "Reza",
                    "user_id": 222222
                }
            }
        }
        self.client.post("/api/v1/webhooks/telegram", json=payload_reza_contact)

        # 10. Reza lists their assigned tasks
        SENT_REPLIES.clear()
        payload_reza_tasks = {
            "message": {
                "message_id": 2003,
                "from": {"id": 222222, "first_name": "Reza", "username": "reza_test"},
                "chat": {"id": 222222, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "text": "/tasks"
            }
        }
        response = self.client.post("/api/v1/webhooks/telegram", json=payload_reza_tasks)
        self.assertEqual(response.status_code, 200)
        self.assertIn("طراحی لوگوی هفته‌یار", SENT_REPLIES[0]["text"])

        # 11. Reza updates the status of the task to DONE
        SENT_REPLIES.clear()
        payload_update = {
            "message": {
                "message_id": 2004,
                "from": {"id": 222222, "first_name": "Reza", "username": "reza_test"},
                "chat": {"id": 222222, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "text": f"/update_task {task_id} DONE"
            }
        }
        response = self.client.post("/api/v1/webhooks/telegram", json=payload_update)
        self.assertEqual(response.status_code, 200)
        self.assertIn("تغییر یافت", SENT_REPLIES[0]["text"])

        # 12. Reza lists their tasks again to verify the status is updated
        SENT_REPLIES.clear()
        payload_reza_tasks_again = {
            "message": {
                "message_id": 2005,
                "from": {"id": 222222, "first_name": "Reza", "username": "reza_test"},
                "chat": {"id": 222222, "type": "private"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "text": "/tasks"
            }
        }
        self.client.post("/api/v1/webhooks/telegram", json=payload_reza_tasks_again)
        self.assertIn("انجام شده", SENT_REPLIES[0]["text"])

        print("=== ALL WEBHOOK BOT FLOW TESTS COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    unittest.main()

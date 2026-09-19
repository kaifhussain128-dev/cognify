import sys
import os
import uuid

# Reconfigure stdout for Windows console UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
from sessions_db import (
    create_session,
    add_session_message,
    get_user_sessions,
    get_session_details,
    update_session_title,
    delete_session,
    migrate_guest_sessions,
    get_study_analytics
)

def run_tests():
    test_guest_id = f"test_guest_{uuid.uuid4().hex[:8]}"
    session_id = f"test_sess_{uuid.uuid4().hex[:8]}"
    
    print("--- TEST 1: Create Session ---")
    s = create_session(session_id, guest_id=test_guest_id, title="New Study Session", pdf_filename="OS_Chapter_2.pdf")
    assert s["id"] == session_id
    assert s["title"] == "New Study Session"
    assert s["pdf_filename"] == "OS_Chapter_2.pdf"
    print("✓ Session created successfully")

    print("--- TEST 2: Add Messages (User & Assistant) ---")
    msg1 = add_session_message(
        session_id=session_id,
        role="user",
        content="What is Round Robin CPU Scheduling and time quantum?",
        guest_id=test_guest_id
    )
    assert msg1["role"] == "user"
    print("✓ User message added and auto-title triggered")

    msg2 = add_session_message(
        session_id=session_id,
        role="assistant",
        content="Round Robin (RR) is a preemptive scheduling algorithm where each process is assigned a fixed time slice called a quantum.",
        engine="🏎️ Groq (llama-3.3-70b-versatile)",
        latency_ms=185,
        sources=[{"title": "OS Scheduling Guide", "page": 4}],
        guest_id=test_guest_id
    )
    assert msg2["role"] == "assistant"
    assert msg2["latency_ms"] == 185
    print("✓ Assistant message stored with engine and citations")

    print("--- TEST 3: Verify Session Details ---")
    details = get_session_details(session_id)
    assert details is not None
    assert len(details["messages"]) == 2
    assert "Round Robin" in details["title"]
    assert details["messages"][1]["latency_ms"] == 185
    assert len(details["messages"][1]["sources"]) == 1
    print(f"✓ Session details verified: Title='{details['title']}', Messages={len(details['messages'])}")

    print("--- TEST 4: List Sessions ---")
    sessions = get_user_sessions(guest_id=test_guest_id)
    assert len(sessions) >= 1
    assert sessions[0]["id"] == session_id
    assert sessions[0]["message_count"] == 2
    print(f"✓ Listed {len(sessions)} session(s) for guest")

    print("--- TEST 5: Rename Session ---")
    renamed = update_session_title(session_id, "Mastering CPU Scheduling")
    assert renamed is True
    details_after_rename = get_session_details(session_id)
    assert details_after_rename["title"] == "Mastering CPU Scheduling"
    print("✓ Session renamed successfully")

    print("--- TEST 6: Study Analytics Aggregation ---")
    analytics = get_study_analytics(guest_id=test_guest_id)
    assert analytics["total_sessions"] >= 1
    assert analytics["total_messages"] >= 2
    assert analytics["user_questions"] >= 1
    assert analytics["ai_answers"] >= 1
    assert analytics["documents_count"] >= 1
    assert "Groq" in list(analytics["engine_breakdown"].keys())[0]
    print(f"✓ Analytics verified: {analytics['total_sessions']} sessions, {analytics['total_messages']} msgs, Engines={analytics['engine_breakdown']}")

    print("--- TEST 7: Delete Session ---")
    deleted = delete_session(session_id)
    assert deleted is True
    assert get_session_details(session_id) is None
    print("✓ Session deleted and verified cascade clean-up")

    print("--- TEST 8: FastAPI HTTP Endpoints via TestClient ---")
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    # 1. Unauthenticated /api/study must be rejected (Auth Gating)
    res_unauth = client.post("/api/study", json={"message": "Hello without login"})
    assert res_unauth.status_code == 401
    assert res_unauth.json()["auth_required"] is True
    print("✓ Unauthenticated /api/study correctly blocked with auth_required")

    # 2. Register user & verify branded User ID (COG-XXXXXX)
    test_user_email = f"student_{uuid.uuid4().hex[:6]}@example.com"
    res_reg = client.post("/auth/register", json={
        "name": "Sarah Connor",
        "email": test_user_email,
        "password": "Password123!"
    })
    assert res_reg.status_code == 200
    user_data = res_reg.json()
    assert user_data["success"] is True
    token = user_data["token"]
    user_info = user_data["user"]
    assert user_info["public_id"].startswith("COG-")
    print(f"✓ New user registered with User ID: {user_info['public_id']}")

    # 3. Test GET and PUT /auth/profile
    res_prof = client.get(f"/auth/profile?token={token}")
    assert res_prof.status_code == 200
    prof = res_prof.json()["profile"]
    assert prof["public_id"] == user_info["public_id"]

    res_prof_update = client.put(f"/auth/profile?token={token}", json={
        "name": "Sarah J. Connor",
        "field_of_study": "Cybernetic Systems",
        "study_goal": "Master Machine Learning and Systems Architecture"
    })
    assert res_prof_update.status_code == 200
    assert res_prof_update.json()["profile"]["field_of_study"] == "Cybernetic Systems"
    print("✓ User profile retrieved and updated in SQLite")

    # 4. Authenticated /api/study with session persistence
    test_api_session = f"api_sess_{uuid.uuid4().hex[:8]}"
    res_study = client.post("/api/study", json={
        "message": "What is Virtual Memory and Paging?",
        "search_mode": "doc",
        "pdf_text": "Virtual memory is a memory management technique that provides an idealized abstraction of the storage resources.",
        "session_id": test_api_session,
        "guest_id": test_guest_id,
        "token": token,
        "pdf_filename": "OS_Concepts.pdf"
    })
    assert res_study.status_code == 200
    study_data = res_study.json()
    assert study_data["success"] is True
    assert study_data["session_id"] == test_api_session
    print("✓ Authenticated /api/study passed with session auto-persistence")

    # 5. Visitor tracking
    res_visit = client.post("/api/track-visit", json={"visitor_id": test_guest_id, "path": "/"})
    assert res_visit.status_code == 200
    assert res_visit.json()["total_visits"] >= 1
    print("✓ Visitor tracking recorded visit")

    # 6. Administrator Login & Dashboard
    res_admin_login = client.post("/auth/login", json={
        "email": "admin@cognify.ai",
        "password": "Admin@Cognify2026"
    })
    assert res_admin_login.status_code == 200
    admin_token = res_admin_login.json()["token"]
    assert res_admin_login.json()["user"]["is_admin"] == 1
    print("✓ Default Administrator account authenticated")

    # Admin dashboard with admin token
    res_dash = client.get(f"/api/admin/dashboard?token={admin_token}")
    assert res_dash.status_code == 200
    dash_data = res_dash.json()["dashboard"]
    assert dash_data["total_visits"] >= 1
    assert dash_data["total_users"] >= 2
    assert len(dash_data["recent_logins"]) >= 1
    print(f"✓ Admin dashboard verified: {dash_data['total_visits']} visits, {dash_data['total_users']} users, {len(dash_data['recent_logins'])} login logs")

    # Admin dashboard forbidden for standard user
    res_dash_forbidden = client.get(f"/api/admin/dashboard?token={token}")
    assert res_dash_forbidden.status_code == 403
    print("✓ Admin dashboard safely forbidden for non-admin accounts")

    # Cleanup
    client.delete(f"/api/sessions/{test_api_session}")
    print("✓ All FastAPI HTTP session routes verified successfully")

    print("\nALL BACKEND, AUTH, PROFILE & ADMIN TESTS PASSED!")

if __name__ == "__main__":
    run_tests()

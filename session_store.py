import uuid
from typing import Any, Dict

from utils import utc_now_iso


class SessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def start_session(self, api_key: str, sector: str, path: str) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "api_key": api_key,
            "sector": sector,
            "started_at": utc_now_iso(),
            "status": "processing",
            "path": path,
        }
        return session_id

    def record_news_count(self, session_id: str, news_count: int) -> None:
        self._sessions[session_id]["news_items"] = news_count

    def complete_session(self, session_id: str, report_source: str) -> None:
        self._sessions[session_id]["status"] = "completed"
        self._sessions[session_id]["completed_at"] = utc_now_iso()
        self._sessions[session_id]["report_source"] = report_source

    def fail_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["status"] = "failed"

    def list_for_key(self, api_key: str) -> Dict[str, Any]:
        mine = {}
        for session_id, data in self._sessions.items():
            if data.get("api_key") != api_key:
                continue
            mine[session_id] = {key: value for key, value in data.items() if key != "api_key"}
        return {"count": len(mine), "sessions": mine}


session_store = SessionStore()

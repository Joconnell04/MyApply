from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Iterable, Optional

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlmodel import Session

from chatkit.server import AttachmentStore, Store
from chatkit.types import Attachment, Page, ThreadItem, ThreadMetadata

from .models import ChatThread, ChatThreadItem


_THREAD_ADAPTER = TypeAdapter(ThreadMetadata)
_THREAD_ITEM_ADAPTER = TypeAdapter(ThreadItem)
class SQLChatStore(Store[Any]):
    """ChatKit Store backed by SQLModel metadata tables."""

    def __init__(self, engine):
        self.engine = engine

    # ------------------------------------------------------------------ ID generation

    def generate_thread_id(self, context: Any) -> str:
        return uuid.uuid4().hex

    def generate_item_id(
        self, item_type: str, thread: ThreadMetadata, context: Any
    ) -> str:
        return uuid.uuid4().hex

    # ------------------------------------------------------------------ Thread helpers

    def _thread_to_model(self, thread: ThreadMetadata) -> ChatThread:
        return ChatThread(
            id=thread.id,
            title=thread.title,
            status=thread.status,
            meta=thread.metadata or {},
            created_at=thread.created_at or datetime.utcnow(),
        )

    def _model_to_thread(self, model: ChatThread) -> ThreadMetadata:
        return _THREAD_ADAPTER.validate_python(
            {
                "id": model.id,
                "title": model.title,
                "status": model.status,
                "metadata": model.meta or {},
                "created_at": model.created_at,
            }
        )

    # ------------------------------------------------------------------ Item helpers

    def _model_to_thread_item(self, model: ChatThreadItem) -> ThreadItem:
        payload = dict(model.payload or {})
        payload.setdefault("id", model.id)
        payload.setdefault("thread_id", model.thread_id)
        payload.setdefault("created_at", model.created_at)
        payload.setdefault("type", model.type)
        return _THREAD_ITEM_ADAPTER.validate_python(payload)

    def _thread_item_to_model(self, item: ThreadItem) -> ChatThreadItem:
        payload = item.model_dump(mode="json")
        return ChatThreadItem(
            id=payload.get("id", uuid.uuid4().hex),
            thread_id=payload["thread_id"],
            type=payload["type"],
            created_at=payload.get("created_at", datetime.utcnow()),
            payload=payload,
        )

    # ------------------------------------------------------------------ Store methods

    async def load_thread(self, thread_id: str, context: Any) -> ThreadMetadata:
        with Session(self.engine) as session:
            model = session.get(ChatThread, thread_id)
            if not model:
                raise ValueError(f"Thread {thread_id} not found.")
            return self._model_to_thread(model)

    async def save_thread(self, thread: ThreadMetadata, context: Any) -> None:
        with Session(self.engine) as session:
            model = session.get(ChatThread, thread.id)
            if model:
                model.title = thread.title
                model.status = thread.status
                model.meta = thread.metadata or {}
                model.created_at = thread.created_at or model.created_at
            else:
                model = self._thread_to_model(thread)
            session.add(model)
            session.commit()

    async def _query_items(
        self,
        session: Session,
        thread_id: str,
        after: Optional[str],
        limit: int,
        order: str,
    ) -> Iterable[ChatThreadItem]:
        query = select(ChatThreadItem).where(ChatThreadItem.thread_id == thread_id)
        order_lower = order.lower()
        if after:
            after_item = session.get(ChatThreadItem, after)
            if after_item:
                comparison = (
                    ChatThreadItem.created_at > after_item.created_at
                    if order_lower == "asc"
                    else ChatThreadItem.created_at < after_item.created_at
                )
                query = query.where(comparison)

        if order_lower == "asc":
            query = query.order_by(ChatThreadItem.created_at.asc(), ChatThreadItem.id.asc())
        else:
            query = query.order_by(ChatThreadItem.created_at.desc(), ChatThreadItem.id.desc())

        if limit:
            query = query.limit(limit + 1)

        return session.exec(query).all()

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: Any,
    ) -> Page[ThreadItem]:
        with Session(self.engine) as session:
            rows = list(
                await self._query_items(session, thread_id, after, limit, order)
            )

            has_more = False
            if limit and len(rows) > limit:
                has_more = True
                rows = rows[:limit]
            after_cursor = rows[-1].id if has_more and rows else None

            items = [self._model_to_thread_item(row) for row in rows]

        return Page(data=items, has_more=has_more, after=after_cursor)

    async def save_attachment(self, attachment: Attachment, context: Any) -> None:
        # Attachments are not persisted yet; integrations can override this store
        # if file uploads are required.
        return None

    async def load_attachment(
        self, attachment_id: str, context: Any
    ) -> Attachment:
        raise ValueError("Attachment support is not enabled for this deployment.")

    async def delete_attachment(self, attachment_id: str, context: Any) -> None:
        return None

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: Any,
    ) -> Page[ThreadMetadata]:
        with Session(self.engine) as session:
            query = select(ChatThread)

            order_lower = order.lower()
            if order_lower == "asc":
                query = query.order_by(ChatThread.created_at.asc(), ChatThread.id.asc())
            else:
                query = query.order_by(ChatThread.created_at.desc(), ChatThread.id.desc())

            if after:
                after_thread = session.get(ChatThread, after)
                if after_thread:
                    comparison = (
                        ChatThread.created_at > after_thread.created_at
                        if order_lower == "asc"
                        else ChatThread.created_at < after_thread.created_at
                    )
                    query = query.where(comparison)

            if limit:
                query = query.limit(limit + 1)

            rows = session.exec(query).all()
            has_more = False
            if limit and len(rows) > limit:
                has_more = True
                rows = rows[:limit]
            after_cursor = rows[-1].id if has_more and rows else None

            data = [self._model_to_thread(row) for row in rows]

        return Page(data=data, has_more=has_more, after=after_cursor)

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: Any
    ) -> None:
        model = self._thread_item_to_model(item)
        with Session(self.engine) as session:
            session.add(model)
            session.commit()

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: Any
    ) -> None:
        payload = item.model_dump(mode="json")
        with Session(self.engine) as session:
            model = session.get(ChatThreadItem, item.id)
            if not model:
                model = self._thread_item_to_model(item)
            else:
                model.payload = payload
                model.created_at = payload.get("created_at", model.created_at)
                model.type = payload.get("type", model.type)
            session.add(model)
            session.commit()

    async def load_item(
        self, thread_id: str, item_id: str, context: Any
    ) -> ThreadItem:
        with Session(self.engine) as session:
            model = session.get(ChatThreadItem, item_id)
            if not model:
                raise ValueError(f"Thread item {item_id} not found.")
            return self._model_to_thread_item(model)

    async def delete_thread(self, thread_id: str, context: Any) -> None:
        with Session(self.engine) as session:
            session.exec(
                ChatThreadItem.__table__.delete().where(
                    ChatThreadItem.thread_id == thread_id
                )
            )
            thread = session.get(ChatThread, thread_id)
            if thread:
                session.delete(thread)
            session.commit()

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: Any
    ) -> None:
        with Session(self.engine) as session:
            model = session.get(ChatThreadItem, item_id)
            if model:
                session.delete(model)
                session.commit()


class NoOpAttachmentStore(AttachmentStore[Any]):
    """Attachment store stub for deployments without file upload support."""

    async def delete_attachment(self, attachment_id: str, context: Any) -> None:
        # Attachments are tracked in the SQLChatStore, so no additional cleanup is required.
        return None

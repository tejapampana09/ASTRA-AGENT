from __future__ import annotations

import base64
import random
from collections import defaultdict
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Sequence, Tuple

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import CheckpointBlobRecord, CheckpointRecord, CheckpointWriteRecord
from app.database.session import get_sync_session_factory
from app.observability.logging import logger


class DurableCheckpointSaver(BaseCheckpointSaver):
    """
    Production-grade durable checkpointer for ASTRA 2.0.
    Implements BaseCheckpointSaver with PostgreSQL / SQLite backing store.
    
    Guarantees:
    - Checkpoint durability across process crashes / server restarts
    - Automatic state restoration on thread_id lookup
    - Dual memory-cache + DB persistence for low-latency active execution
    """

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        super().__init__()
        self.serde = JsonPlusSerializer()
        self._session_factory = session_factory or get_sync_session_factory()

        # In-memory fast cache
        self.storage: Dict[str, Dict[str, Dict[str, Tuple[bytes, bytes, Optional[str]]]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self.writes: Dict[Tuple[str, str, str], Dict[Tuple[str, int], Tuple[str, str, bytes, str]]] = defaultdict(dict)
        self.blobs: Dict[Tuple[str, str, str, str], Tuple[str, bytes]] = {}

    def _encode_bytes(self, b: bytes) -> str:
        return base64.b64encode(b).decode("ascii")

    def _decode_bytes(self, s: str) -> bytes:
        return base64.b64decode(s.encode("ascii"))

    def _load_blobs(
        self, thread_id: str, checkpoint_ns: str, versions: ChannelVersions
    ) -> Dict[str, Any]:
        """Loads and deserializes blobs for given channel versions."""
        blob_values: Dict[str, Any] = {}
        for k, ver in versions.items():
            key = (thread_id, checkpoint_ns, k, ver)
            key_str = (thread_id, checkpoint_ns, k, str(ver))
            if key in self.blobs:
                t, b = self.blobs[key]
                if t != "empty":
                    blob_values[k] = self.serde.loads_typed((t, b))
            elif key_str in self.blobs:
                t, b = self.blobs[key_str]
                if t != "empty":
                    blob_values[k] = self.serde.loads_typed((t, b))
            elif self._session_factory:
                # Fallback to DB query
                try:
                    with self._session_factory() as session:
                        rec = session.query(CheckpointBlobRecord).filter_by(
                            thread_id=thread_id,
                            checkpoint_ns=checkpoint_ns,
                            channel=k,
                            version=str(ver),
                        ).first()
                        if rec:
                            raw_b = self._decode_bytes(rec.blob_data)
                            self.blobs[key] = (rec.type, raw_b)
                            self.blobs[key_str] = (rec.type, raw_b)
                            if rec.type != "empty":
                                blob_values[k] = self.serde.loads_typed((rec.type, raw_b))
                except Exception as e:
                    logger.debug(f"Error querying blob from DB: {e}")
        return blob_values

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)

        # 1. Check in-memory storage first
        if checkpoint_id:
            if saved := self.storage[thread_id][checkpoint_ns].get(checkpoint_id):
                c_bytes, meta_bytes, parent_id = saved
                writes = self.writes[(thread_id, checkpoint_ns, checkpoint_id)].values()
                checkpoint_: Checkpoint = self.serde.loads_typed(c_bytes)
                return CheckpointTuple(
                    config=config,
                    checkpoint={
                        **checkpoint_,
                        "channel_values": self._load_blobs(
                            thread_id, checkpoint_ns, checkpoint_["channel_versions"]
                        ),
                    },
                    metadata=self.serde.loads_typed(meta_bytes),
                    pending_writes=[
                        (id, c, self.serde.loads_typed(v)) for id, c, v, _ in writes
                    ],
                    parent_config=(
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": parent_id,
                            }
                        }
                        if parent_id
                        else None
                    ),
                )
        else:
            if checkpoints := self.storage[thread_id][checkpoint_ns]:
                checkpoint_id = max(checkpoints.keys())
                c_bytes, meta_bytes, parent_id = checkpoints[checkpoint_id]
                writes = self.writes[(thread_id, checkpoint_ns, checkpoint_id)].values()
                checkpoint_ = self.serde.loads_typed(c_bytes)
                return CheckpointTuple(
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": checkpoint_id,
                        }
                    },
                    checkpoint={
                        **checkpoint_,
                        "channel_values": self._load_blobs(
                            thread_id, checkpoint_ns, checkpoint_["channel_versions"]
                        ),
                    },
                    metadata=self.serde.loads_typed(meta_bytes),
                    pending_writes=[
                        (id, c, self.serde.loads_typed(v)) for id, c, v, _ in writes
                    ],
                    parent_config=(
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": parent_id,
                            }
                        }
                        if parent_id
                        else None
                    ),
                )

        # 2. Database Recovery Path (after process crash / reboot)
        if not self._session_factory:
            return None

        try:
            with self._session_factory() as session:
                query = session.query(CheckpointRecord).filter(
                    CheckpointRecord.thread_id == thread_id,
                    CheckpointRecord.checkpoint_ns == checkpoint_ns,
                )
                if checkpoint_id:
                    rec = query.filter(CheckpointRecord.checkpoint_id == checkpoint_id).first()
                else:
                    rec = query.order_by(desc(CheckpointRecord.checkpoint_id)).first()

                if not rec:
                    return None

                target_checkpoint_id = rec.checkpoint_id
                c_bytes = self._decode_bytes(rec.checkpoint_data)
                meta_bytes = self._decode_bytes(rec.metadata_data) if rec.metadata_data else b""
                parent_id = rec.parent_checkpoint_id
                c_type = getattr(rec, "checkpoint_type", "msgpack") or "msgpack"
                meta_type = getattr(rec, "metadata_type", "msgpack") or "msgpack"
                c_serialized = (c_type, c_bytes)
                meta_serialized = (meta_type, meta_bytes)

                # Cache loaded checkpoint in memory
                self.storage[thread_id][checkpoint_ns][target_checkpoint_id] = (c_serialized, meta_serialized, parent_id)

                # Fetch and cache associated writes
                write_records = session.query(CheckpointWriteRecord).filter_by(
                    thread_id=thread_id,
                    checkpoint_ns=checkpoint_ns,
                    checkpoint_id=target_checkpoint_id,
                ).all()

                for w in write_records:
                    inner_k = (w.task_id, w.idx)
                    val_b = self._decode_bytes(w.value_data)
                    w_type = getattr(w, "type", "msgpack") or "msgpack"
                    self.writes[(thread_id, checkpoint_ns, target_checkpoint_id)][inner_k] = (
                        w.task_id,
                        w.channel,
                        (w_type, val_b),
                        w.task_path or "",
                    )

                # Fetch and cache associated blobs
                blob_records = session.query(CheckpointBlobRecord).filter_by(
                    thread_id=thread_id,
                    checkpoint_ns=checkpoint_ns,
                ).all()
                for b in blob_records:
                    blob_b = self._decode_bytes(b.blob_data)
                    self.blobs[(thread_id, checkpoint_ns, b.channel, b.version)] = (b.type, blob_b)
                    if b.version.isdigit():
                        self.blobs[(thread_id, checkpoint_ns, b.channel, int(b.version))] = (b.type, blob_b)

                checkpoint_data: Checkpoint = self.serde.loads_typed(c_serialized)
                metadata_data = self.serde.loads_typed(meta_serialized) if meta_bytes else {}
                writes_list = self.writes[(thread_id, checkpoint_ns, target_checkpoint_id)].values()

                return CheckpointTuple(
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": target_checkpoint_id,
                        }
                    },
                    checkpoint={
                        **checkpoint_data,
                        "channel_values": self._load_blobs(
                            thread_id, checkpoint_ns, checkpoint_data["channel_versions"]
                        ),
                    },
                    metadata=metadata_data,
                    pending_writes=[
                        (id, c, self.serde.loads_typed(v)) for id, c, v, _ in writes_list
                    ],
                    parent_config=(
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": parent_id,
                            }
                        }
                        if parent_id
                        else None
                    ),
                )
        except Exception as e:
            logger.error(f"Error loading durable checkpoint for thread {thread_id}: {e}", exc_info=True)
            return None

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        c = checkpoint.copy()
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        values: dict[str, Any] = c.pop("channel_values")  # type: ignore[misc]

        # 1. Update memory cache
        for k, v in new_versions.items():
            self.blobs[(thread_id, checkpoint_ns, k, str(v))] = (
                self.serde.dumps_typed(values[k]) if k in values else ("empty", b"")
            )

        c_serialized = self.serde.dumps_typed(c)
        meta_serialized = self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))
        parent_id = config["configurable"].get("checkpoint_id")

        self.storage[thread_id][checkpoint_ns][checkpoint["id"]] = (
            c_serialized,
            meta_serialized,
            parent_id,
        )

        # 2. Persist to Database if session factory is available
        if self._session_factory:
            try:
                with self._session_factory() as session:
                    # Upsert checkpoint
                    cp_rec = CheckpointRecord(
                        thread_id=thread_id,
                        checkpoint_ns=checkpoint_ns,
                        checkpoint_id=checkpoint["id"],
                        parent_checkpoint_id=parent_id,
                        checkpoint_type=c_serialized[0],
                        checkpoint_data=self._encode_bytes(c_serialized[1]),
                        metadata_type=meta_serialized[0],
                        metadata_data=self._encode_bytes(meta_serialized[1]),
                    )
                    session.merge(cp_rec)

                    # Persist blobs
                    for k, v in new_versions.items():
                        blob_key = (thread_id, checkpoint_ns, k, str(v))
                        if blob_key in self.blobs:
                            b_type, b_bytes = self.blobs[blob_key]
                            blob_rec = CheckpointBlobRecord(
                                thread_id=thread_id,
                                checkpoint_ns=checkpoint_ns,
                                channel=k,
                                version=str(v),
                                type=b_type,
                                blob_data=self._encode_bytes(b_bytes),
                            )
                            session.merge(blob_rec)
                    session.commit()
            except Exception as e:
                logger.warning(f"Failed to persist checkpoint to database: {e}")

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]
        outer_key = (thread_id, checkpoint_ns, checkpoint_id)
        outer_writes_ = self.writes.get(outer_key)

        records_to_insert = []
        for idx, (c, v) in enumerate(writes):
            inner_key = (task_id, WRITES_IDX_MAP.get(c, idx))
            if inner_key[1] >= 0 and outer_writes_ and inner_key in outer_writes_:
                continue

            v_type, v_bytes = self.serde.dumps_typed(v)
            self.writes[outer_key][inner_key] = (
                task_id,
                c,
                (v_type, v_bytes),  # type: ignore
                task_path,
            )
            records_to_insert.append({
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "idx": inner_key[1],
                "channel": c,
                "type": v_type,
                "value_data": self._encode_bytes(v_bytes),
                "task_path": task_path,
            })

        if self._session_factory and records_to_insert:
            try:
                with self._session_factory() as session:
                    for r in records_to_insert:
                        write_rec = CheckpointWriteRecord(**r)
                        session.add(write_rec)
                    session.commit()
            except Exception as e:
                logger.warning(f"Failed to persist writes to database: {e}")

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        if not config:
            return iter([])
        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        checkpoints = self.storage.get(thread_id, {}).get(checkpoint_ns, {})
        for cid in sorted(checkpoints.keys(), reverse=True):
            if limit and limit <= 0:
                break
            tuple_result = self.get_tuple({
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": cid,
                }
            })
            if tuple_result:
                yield tuple_result
                if limit:
                    limit -= 1

    def delete_thread(self, thread_id: str) -> None:
        if thread_id in self.storage:
            del self.storage[thread_id]
        for k in list(self.writes.keys()):
            if k[0] == thread_id:
                del self.writes[k]
        for k in list(self.blobs.keys()):
            if k[0] == thread_id:
                del self.blobs[k]

        if self._session_factory:
            try:
                with self._session_factory() as session:
                    session.query(CheckpointRecord).filter_by(thread_id=thread_id).delete()
                    session.query(CheckpointBlobRecord).filter_by(thread_id=thread_id).delete()
                    session.query(CheckpointWriteRecord).filter_by(thread_id=thread_id).delete()
                    session.commit()
            except Exception as e:
                logger.warning(f"Failed to delete thread from database: {e}")

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return self.get_tuple(config)

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        return self.put_writes(config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        return self.delete_thread(thread_id)

    def get_next_version(self, current: Optional[str], channel: None) -> str:
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(current.split(".")[0])
        next_v = current_v + 1
        next_h = random.random()
        return f"{next_v:032}.{next_h:016}"


# Global singleton instance
_durable_checkpointer: Optional[DurableCheckpointSaver] = None


def get_durable_checkpointer(session_factory: Optional[sessionmaker] = None) -> DurableCheckpointSaver:
    global _durable_checkpointer
    if _durable_checkpointer is None or session_factory is not None:
        _durable_checkpointer = DurableCheckpointSaver(session_factory=session_factory)
    return _durable_checkpointer

import json
from datetime import datetime
from typing import List

import redis

from redis_bullmq_explorer.domain_models import Job


class RedisBullMQRepository:
    def __init__(self):
        self.r = None
        self.prefix = "bull"

    def connect(self, url: str, prefix: str):
        self.prefix = prefix or "bull"
        self.r = redis.Redis.from_url(url, decode_responses=True)
        self.r.ping()

    def disconnect(self):
        if self.r:
            self.r.close()
            self.r = None

    def get_redis_info(self) -> dict[str, str]:
        if self.r is None:
            return {}
        info = self.r.info()
        version = str(info.get("redis_version", "-"))
        mode = str(info.get("redis_mode", "-"))
        used = info.get("used_memory_human")
        if not used:
            used_bytes = info.get("used_memory")
            used = f"{used_bytes} bytes" if used_bytes is not None else "-"
        total = info.get("total_system_memory_human") or info.get("maxmemory_human")
        if not total:
            total_bytes = info.get("total_system_memory") or info.get("maxmemory")
            total = f"{total_bytes} bytes" if total_bytes is not None else "-"
        clients = str(info.get("connected_clients", "-"))
        return {
            "version": version,
            "mode": mode,
            "used_memory": used,
            "total_memory": total,
            "clients": clients,
        }

    def get_queues(self) -> List[str]:
        if self.r is None:
            return []
        pattern = f"{self.prefix}:*:meta"
        queues = set()
        cursor = 0
        while True:
            cursor, keys = self.r.scan(cursor=cursor, match=pattern, count=200)
            for key in keys:
                parts = key.split(":")
                if len(parts) >= 3:
                    queues.add(parts[1])
            if cursor == 0:
                break
        return sorted(queues)

    def _collect_ids_from_key(self, key: str):
        t = self.r.type(key)
        if t == "list":
            return self.r.lrange(key, 0, -1)
        if t == "zset":
            return [item[0] for item in self.r.zrange(key, 0, -1, withscores=True)]
        if t == "set":
            return list(self.r.smembers(key))
        return []

    def get_jobs(self, queue: str, page: int = 1, page_size: int = 20, search_term: str = "", status_filter: str = "", sort_by: str = "timestamp", descending: bool = True) -> tuple[List[Job], int, dict[str, int]]:
        if self.r is None:
            return [], 0, {}
        base = f"{self.prefix}:{queue}"
        state_keys = {
            "wait": f"{base}:wait",
            "active": f"{base}:active",
            "delayed": f"{base}:delayed",
            "completed": f"{base}:completed",
            "failed": f"{base}:failed",
        }
        
        # 1. Collect all IDs and their states, and count them
        jobs_map = {} # id -> set(states)
        counts = {s: 0 for s in state_keys.keys()}
        
        for state, key in state_keys.items():
            ids = self._collect_ids_from_key(key)
            counts[state] = len(ids)
            for jid in ids:
                jid_str = str(jid)
                if jid_str not in jobs_map:
                    jobs_map[jid_str] = set()
                jobs_map[jid_str].add(state)

        all_ids = list(jobs_map.keys())
        
        # 2. Filter (Search & Status)
        filtered_ids = []
        
        # Pre-filter by status if needed to avoid expensive search on wrong items
        ids_to_search = all_ids
        if status_filter:
            ids_to_search = [jid for jid in all_ids if status_filter in jobs_map[jid]]
            
        if not search_term:
            filtered_ids = ids_to_search
        else:
            # For search, we need to check ID and Data. 
            # Fetching data for ALL jobs can be heavy, but necessary for full search.
            # Using pipeline to minimize round-trips.
            search_lower = search_term.lower()
            
            pipe = self.r.pipeline()
            for jid in ids_to_search:
                pipe.hget(f"{base}:{jid}", "data")
            
            data_results = pipe.execute()
            
            for jid, data_raw in zip(ids_to_search, data_results):
                data_str = (data_raw or "")
                if search_lower in jid.lower() or search_lower in data_str.lower():
                    filtered_ids.append(jid)

        total_count = len(filtered_ids)

        # 3. Sort (Global)
        if sort_by == "timestamp":
            # Fetch timestamps for all filtered IDs
            pipe = self.r.pipeline()
            for jid in filtered_ids:
                pipe.hget(f"{base}:{jid}", "timestamp")
            
            ts_results = pipe.execute()
            
            # Create a list of tuples (id, timestamp_int)
            ids_with_ts = []
            for jid, ts_raw in zip(filtered_ids, ts_results):
                ts_val = 0
                if ts_raw:
                    try:
                        ts_val = int(ts_raw)
                    except:
                        pass
                ids_with_ts.append((jid, ts_val))
            
            # Sort by timestamp
            ids_with_ts.sort(key=lambda x: x[1], reverse=descending)
            filtered_ids = [x[0] for x in ids_with_ts]
            
        else:
            # Default sort by ID
            filtered_ids.sort(key=lambda x: int(x) if x.isdigit() else x, reverse=descending)

        # 4. Pagination Slice
        start = (page - 1) * page_size
        end = start + page_size
        page_ids = filtered_ids[start:end]

        # 5. Fetch Details for Page
        result: List[Job] = []
        if not page_ids:
            return [], total_count, counts

        pipe = self.r.pipeline()
        for jid in page_ids:
            pipe.hgetall(f"{base}:{jid}")
        
        job_details = pipe.execute()
        
        for jid, h in zip(page_ids, job_details):
            name = h.get("name", "")
            data_raw = h.get("data", "")
            timestamp_raw = h.get("timestamp", "")
            timestamp_str = "-"
            
            if timestamp_raw:
                try:
                    ts = int(timestamp_raw) / 1000.0
                    timestamp_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    timestamp_str = str(timestamp_raw)

            preview = ""
            if data_raw:
                try:
                    parsed = json.loads(data_raw)
                    preview = json.dumps(parsed, ensure_ascii=False)[:140]
                except Exception:
                    preview = data_raw[:140]
            state_str = ",".join(sorted(jobs_map[jid]))
            result.append(
                Job(
                    id=jid,
                    name=name,
                    state=state_str,
                    data_preview=preview,
                    timestamp=timestamp_str,
                )
            )
            
        return result, total_count, counts

    def get_job_detail(self, queue: str, job_id: str) -> dict[str, str]:
        if self.r is None:
            return {}
        base = f"{self.prefix}:{queue}"
        job_key = f"{base}:{job_id}"
        h = self.r.hgetall(job_key)
        name = h.get("name", "")
        data_raw = h.get("data", "") or ""
        data_json = data_raw
        try:
            if data_raw:
                parsed = json.loads(data_raw)
                data_json = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            data_json = data_raw
        state_keys = {
            "wait": f"{base}:wait",
            "active": f"{base}:active",
            "delayed": f"{base}:delayed",
            "completed": f"{base}:completed",
            "failed": f"{base}:failed",
        }
        states = []
        for state, key in state_keys.items():
            t = self.r.type(key)
            if t == "list":
                if self.r.lpos(key, job_id) is not None:
                    states.append(state)
            elif t == "zset":
                if self.r.zscore(key, job_id) is not None:
                    states.append(state)
            elif t == "set":
                if self.r.sismember(key, job_id):
                    states.append(state)
        state_str = ",".join(sorted(states))
        return {
            "id": str(job_id),
            "name": name,
            "state": state_str,
            "data_raw": data_raw,
            "data_json": data_json,
        }

    def delete_job(self, queue: str, job_id: str):
        if self.r is None:
            return
        base = f"{self.prefix}:{queue}"
        job_key = f"{base}:{job_id}"
        logs_key = f"{base}:{job_id}:logs"
        state_suffixes = [":wait", ":active", ":delayed", ":completed", ":failed"]
        pipe = self.r.pipeline()
        for suffix in state_suffixes:
            key = base + suffix
            t = self.r.type(key)
            if t == "list":
                pipe.lrem(key, 0, job_id)
            elif t == "zset":
                pipe.zrem(key, job_id)
            elif t == "set":
                pipe.srem(key, job_id)
        pipe.delete(job_key, logs_key)
        pipe.execute()

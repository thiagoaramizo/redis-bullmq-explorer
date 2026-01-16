from typing import List

from redis_bullmq_explorer.domain_models import Queue, Job
from redis_bullmq_explorer.infrastructure_redis_bullmq import RedisBullMQRepository


class ExplorerService:
    def __init__(self, repository: RedisBullMQRepository):
        self.repository = repository

    def connect(self, url: str, prefix: str):
        self.repository.connect(url, prefix)

    def disconnect(self):
        self.repository.disconnect()

    def get_redis_info(self) -> dict[str, str]:
        return self.repository.get_redis_info()

    def list_queues(self) -> List[Queue]:
        names = self.repository.get_queues()
        return [Queue(name=n) for n in names]

    def list_jobs(self, queue: Queue, page: int = 1, page_size: int = 20, search_term: str = "", status_filter: str = "", sort_by: str = "timestamp", descending: bool = True) -> tuple[List[Job], int, dict[str, int]]:
        return self.repository.get_jobs(queue.name, page, page_size, search_term, status_filter, sort_by, descending)

    def delete_job(self, queue: Queue, job_id: str):
        self.repository.delete_job(queue.name, job_id)

    def get_job_detail(self, queue: Queue, job_id: str):
        return self.repository.get_job_detail(queue.name, job_id)

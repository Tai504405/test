import os
import json
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BasePublisher(ABC):
    """Abstract Base Class for Social Media Publishers.
    Allows swapping to real platform APIs (Facebook, X, Threads) without modifying orchestrator logic.
    """
    @abstractmethod
    def publish(self, account_id: str, content: str, metadata: dict = None) -> bool:
        pass

class MockPublisher(BasePublisher):
    """Mock Publisher class for local testing and batch export.
    Exports approved social media posts to local JSON/markdown files and logs publication details.
    """
    def __init__(self, export_dir: str = "outputs"):
        self.export_dir = export_dir
        os.makedirs(self.export_dir, exist_ok=True)

    def publish(self, account_id: str, content: str, metadata: dict = None) -> bool:
        export_file = os.path.join(self.export_dir, f"{account_id}_posts.json")
        post_entry = {
            "account_id": account_id,
            "content": content,
            "metadata": metadata or {}
        }
        
        existing_posts = []
        if os.path.exists(export_file):
            try:
                with open(export_file, "r", encoding="utf-8") as f:
                    existing_posts = json.load(f)
            except Exception:
                existing_posts = []

        existing_posts.append(post_entry)
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(existing_posts, f, ensure_ascii=False, indent=2)

        logger.info(f"✔️ Publisher (Mock): Đã xuất bản và xuất file thành công tại: {export_file}")
        return True

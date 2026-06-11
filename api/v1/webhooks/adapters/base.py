from abc import ABC, abstractmethod
from app.api.v1.webhooks.schemas import InternalMessage


class BaseAdapter(ABC):
    @abstractmethod
    def parse(self, payload: dict) -> InternalMessage:
        """
        Parses raw payload from platform into canonical InternalMessage.
        Must raise ValueError or KeyError if payload structure is invalid.
        """
        raise NotImplementedError

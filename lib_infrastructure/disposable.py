

from abc import ABC, abstractmethod


class Disposable(ABC):

    @abstractmethod
    def dispose(self) -> None:
        pass
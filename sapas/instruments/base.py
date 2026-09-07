from abc import ABC, abstractmethod


class BaseInstrument(ABC):
    """
    Abstract base class for all hardware instruments in Sapas.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish communication with the physical instrument."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Safely release the connection to the instrument."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if connection is active."""
        pass

from abc import ABC, abstractmethod


class BaseTransport(ABC):
    """
    Abstract interface for physical communication channels (TCP, Serial, VISA).
    """

    @abstractmethod
    def connect(self) -> None:
        """Open the physical communication link."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the physical communication link."""
        pass

    @abstractmethod
    def write(self, command: str) -> None:
        """Send a raw command string to the instrument."""
        pass

    @abstractmethod
    def read(self) -> str:
        """Read a response line/data from the instrument."""
        pass

    def query(self, command: str) -> str:
        """Convenience method to write a query command and return the response."""
        self.write(command)
        return self.read()

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connection is open."""
        pass

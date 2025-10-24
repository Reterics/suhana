"""
Dependency Injection Container for Suhana

This module provides a simple dependency injection container to manage
dependencies across the application, improving testability and modularity.

The DIContainer is used in the codebase to:
1. Register and retrieve components like vectorstore_manager, memory stores, and LLM backends
2. Provide type checking for dependencies
3. Support testing by allowing dependencies to be mocked

While it's a simple implementation, it provides valuable functionality for dependency management.
"""

from typing import Dict, Any, Callable, Type, TypeVar

T = TypeVar('T')

class DIContainer:
    """
    A simple dependency injection container that manages application dependencies.

    This container allows registering and retrieving dependencies, making it easier
    to replace implementations for testing and improving modularity.
    """

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, instance: Any) -> None:
        """
        Register an instance with the container.

        Args:
            name: The name to register the instance under
            instance: The instance to register
        """
        self._services[name] = instance

    def register_factory(self, name: str, factory: Callable[..., Any]) -> None:
        """
        Register a factory function that creates an instance when needed.

        Args:
            name: The name to register the factory under
            factory: A callable that returns an instance
        """
        self._factories[name] = factory

    def get(self, name: str) -> Any:
        """
        Get an instance from the container.

        Args:
            name: The name of the instance to retrieve

        Returns:
            The registered instance or a new instance created by the factory

        Raises:
            KeyError: If the name is not registered
        """
        if name in self._services:
            return self._services[name]

        if name in self._factories:
            instance = self._factories[name](self)
            self._services[name] = instance
            return instance

        raise KeyError(f"No service or factory registered for '{name}'")

    def get_or_default(self, name: str, default: Any = None) -> Any:
        """
        Get an instance from the container or return a default value if not found.

        Args:
            name: The name of the instance to retrieve
            default: The default value to return if the name is not registered

        Returns:
            The registered instance or the default value
        """
        try:
            return self.get(name)
        except KeyError:
            return default

    def get_typed(self, name: str, cls: Type[T]) -> T:
        """
        Get an instance from the container with type checking.

        Args:
            name: The name of the instance to retrieve
            cls: The expected type of the instance

        Returns:
            The registered instance cast to the expected type

        Raises:
            KeyError: If the name is not registered
            TypeError: If the instance is not of the expected type
        """
        instance = self.get(name)
        if not isinstance(instance, cls):
            raise TypeError(f"Service '{name}' is not of type {cls.__name__}")
        return instance

# Create a global container instance
container = DIContainer()

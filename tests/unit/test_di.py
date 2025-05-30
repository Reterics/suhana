import pytest
from typing import Protocol, runtime_checkable


from engine.di import DIContainer

# Define a protocol for testing
@runtime_checkable
class ServiceInterface(Protocol):
    def get_value(self) -> str:
        ...

# Concrete implementation of the test service
class Service:
    def __init__(self, value: str = "default"):
        self.value = value

    def get_value(self) -> str:
        return self.value

# Another implementation for testing type checking
class AnotherService:
    def get_value(self) -> str:
        return "another"

@pytest.fixture
def container():
    """Create a fresh container for each test."""
    return DIContainer()

def test_register_and_get():
    """Test basic registration and retrieval."""
    container = DIContainer()
    service = Service("test_value")

    container.register("test_service", service)
    retrieved = container.get("test_service")

    assert retrieved is service
    assert retrieved.get_value() == "test_value"

def test_get_nonexistent_service():
    """Test that getting a nonexistent service raises KeyError."""
    container = DIContainer()

    with pytest.raises(KeyError):
        container.get("nonexistent")

def test_register_factory():
    """Test registering and using a factory function."""
    container = DIContainer()

    def factory(_):
        return Service("factory_created")

    container.register_factory("factory_service", factory)
    service = container.get("factory_service")

    assert isinstance(service, Service)
    assert service.get_value() == "factory_created"

    # Second retrieval should return the same instance
    service2 = container.get("factory_service")
    assert service2 is service

def test_get_or_default():
    """Test get_or_default method."""
    container = DIContainer()
    default_service = Service("default")

    # Should return default for nonexistent service
    result = container.get_or_default("nonexistent", default_service)
    assert result is default_service

    # Should return registered service if it exists
    registered_service = Service("registered")
    container.register("test_service", registered_service)
    result = container.get_or_default("test_service", default_service)
    assert result is registered_service

def test_get_typed():
    """Test get_typed method with correct type."""
    container = DIContainer()
    service = Service()
    container.register("test_service", service)

    # Should work with correct type
    typed_service = container.get_typed("test_service", Service)
    assert typed_service is service

    # Should work with protocol
    protocol_service = container.get_typed("test_service", ServiceInterface)
    assert protocol_service is service

def test_get_typed_wrong_type():
    """Test get_typed method with incorrect type."""
    container = DIContainer()
    service = Service()
    container.register("test_service", service)

    # Should raise TypeError for wrong type
    with pytest.raises(TypeError):
        container.get_typed("test_service", str)

def test_factory_with_container_arg():
    """Test that factory functions receive the container as an argument."""
    container = DIContainer()

    # Create a factory that uses the container to get another service
    container.register("dependency", Service("dependency"))

    def factory(container):
        # This factory uses the container to get another service
        dependency = container.get("dependency")
        return Service(f"factory_with_{dependency.get_value()}")

    container.register_factory("factory_service", factory)

    # Get the service, which should trigger the factory
    service = container.get("factory_service")

    assert service.get_value() == "factory_with_dependency"

def test_get_or_default_with_none():
    """Test get_or_default with None as the default value."""
    container = DIContainer()

    # Should return None for nonexistent service when default is None
    result = container.get_or_default("nonexistent")
    assert result is None

def test_get_typed_nonexistent():
    """Test get_typed with a nonexistent service."""
    container = DIContainer()

    # Should raise KeyError for nonexistent service
    with pytest.raises(KeyError):
        container.get_typed("nonexistent", Service)

def test_global_container():
    """Test that the global container instance exists."""
    from engine.di import container as global_container

    assert isinstance(global_container, DIContainer)

    # Register a service to the global container
    service = Service("global")
    global_container.register("global_test", service)

    # Retrieve it to verify
    retrieved = global_container.get("global_test")
    assert retrieved is service

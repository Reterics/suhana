import pytest
from abc import ABC

from engine.interfaces import (
    VectorStoreInterface,
    VectorStoreManagerInterface,
    MemoryStoreInterface,
    LLMBackendInterface
)

def test_interfaces_are_abstract():
    """Test that all interfaces are abstract base classes."""
    assert issubclass(VectorStoreInterface, ABC)
    assert issubclass(VectorStoreManagerInterface, ABC)
    assert issubclass(MemoryStoreInterface, ABC)
    assert issubclass(LLMBackendInterface, ABC)

def test_cannot_instantiate_interfaces_directly():
    """Test that interfaces cannot be instantiated directly."""
    with pytest.raises(TypeError):
        VectorStoreInterface()

    with pytest.raises(TypeError):
        VectorStoreManagerInterface()

    with pytest.raises(TypeError):
        MemoryStoreInterface()

    with pytest.raises(TypeError):
        LLMBackendInterface()

def test_vector_store_interface_implementation():
    """Test that VectorStoreInterface can be properly implemented."""
    class ConcreteVectorStore(VectorStoreInterface):
        def similarity_search_with_score(self, query, k=4):
            return [("document1", 0.9), ("document2", 0.8)]

    # Should not raise any errors
    store = ConcreteVectorStore()
    result = store.similarity_search_with_score("test query")

    assert len(result) == 2
    assert result[0][0] == "document1"
    assert result[0][1] == 0.9

def test_vector_store_manager_interface_implementation():
    """Test that VectorStoreManagerInterface can be properly implemented."""
    class ConcreteVectorStoreManager(VectorStoreManagerInterface):
        @property
        def current_vector_mode(self):
            return "test_mode"

        def get_vectorstore(self, profile=None):
            return None

        def reset_vectorstore(self):
            pass

    # Should not raise any errors
    manager = ConcreteVectorStoreManager()
    assert manager.current_vector_mode == "test_mode"
    assert manager.get_vectorstore() is None

def test_memory_store_interface_implementation():
    """Test that MemoryStoreInterface can be properly implemented."""
    class ConcreteMemoryStore(MemoryStoreInterface):
        def search_memory(self, query, k=10):
            return ["memory1", "memory2"]

    # Should not raise any errors
    store = ConcreteMemoryStore()
    result = store.search_memory("test query")

    assert len(result) == 2
    assert result[0] == "memory1"

def test_llm_backend_interface_implementation():
    """Test that LLMBackendInterface can be properly implemented."""
    class ConcreteLLMBackend(LLMBackendInterface):
        def query(self, user_input, system_prompt, profile, settings, force_stream=False):
            return f"Response to: {user_input}"

    # Should not raise any errors
    backend = ConcreteLLMBackend()
    result = backend.query(
        "test query",
        "You are a helpful assistant",
        {"name": "User"},
        {"setting": "value"}
    )

    assert result == "Response to: test query"

def test_llm_backend_interface_streaming_implementation():
    """Test that LLMBackendInterface can be implemented with streaming support."""
    class StreamingLLMBackend(LLMBackendInterface):
        def query(self, user_input, system_prompt, profile, settings, force_stream=False):
            if force_stream:
                def generator():
                    for word in ["Response", "to:", user_input]:
                        yield word + " "
                return generator()
            else:
                return f"Response to: {user_input}"

    # Test non-streaming mode
    backend = StreamingLLMBackend()
    result = backend.query(
        "test query",
        "You are a helpful assistant",
        {"name": "User"},
        {"setting": "value"}
    )
    assert result == "Response to: test query"

    # Test streaming mode
    generator = backend.query(
        "test query",
        "You are a helpful assistant",
        {"name": "User"},
        {"setting": "value"},
        force_stream=True
    )

    # Collect the streamed output
    streamed_output = "".join(list(generator))
    assert streamed_output == "Response to: test query "

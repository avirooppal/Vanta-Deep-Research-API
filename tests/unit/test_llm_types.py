from core.llm.types import Message, LLMConfig


def test_message_creation():
    m = Message(role="user", content="hello")
    assert m.role == "user"


def test_llm_config_defaults():
    cfg = LLMConfig(
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4o",
    )
    assert cfg.temperature == 0.2
    assert cfg.max_concurrent == 3

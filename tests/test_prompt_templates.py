from llama_manager.core.chat.prompt_templates import PromptTemplateAdapter


def test_prompt_template_adapter_uses_custom_registry_handler():
    def _custom_handler(model_name, request_payload, request_body):
        request_payload["chat_template"] = "my-template"
        request_payload["template_model"] = model_name
        return request_payload

    adapter = PromptTemplateAdapter(registry={"custom": _custom_handler})
    payload = {"messages": [{"role": "user", "content": "hi"}]}

    result = adapter.apply("qwen", "custom", payload, {})

    assert result["chat_template"] == "my-template"
    assert result["template_model"] == "qwen"


def test_prompt_template_adapter_maps_gpt_oss_alias_to_chatml():
    adapter = PromptTemplateAdapter()
    payload = {"messages": [{"role": "user", "content": "hi"}]}

    result = adapter.apply("gpt-oss-20b", "gpt-oss", payload, {})

    assert result["chat_template"] == "chatml"

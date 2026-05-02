import config
from openai import OpenAI

class LLMRouter:
    @staticmethod
    def get_client(provider="groq"):
        app_config = config.config

        if provider == "groq":
            api_key = app_config.get("groq_api_key", "")
            base_url = "https://api.groq.com/openai/v1"
        elif provider == "nvidia":
            api_key = app_config.get("nvidia_api_key", "")
            base_url = "https://integrate.api.nvidia.com/v1"
        elif provider == "glm":
            api_key = app_config.get("glm_api_key", "")
            base_url = "https://open.bigmodel.cn/api/paas/v4/"
        else:
            raise ValueError(f"Unknown provider: {provider}")

        return OpenAI(api_key=api_key, base_url=base_url)

    @staticmethod
    def complete(prompt, system, provider="groq", model=None, stream=False):
        client = LLMRouter.get_client(provider)

        if model is None:
            if provider == "groq":
                model = "llama-3.1-8b-instant"
            elif provider == "nvidia":
                model = "meta/llama-3.3-70b-instruct"
            elif provider == "glm":
                model = "glm-4-flash"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if prompt:
            messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=stream,
            temperature=0.7,
            max_tokens=1024
        )
        return response

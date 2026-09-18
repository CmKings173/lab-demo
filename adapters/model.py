class FakeModelClient:
    def __init__(self, response: str = "fake-model-response") -> None:
        self.response = response

    def generate(self, prompt: str) -> str:
        return self.response


class VLLMModelClient:
    """Reserved for the local vLLM endpoint; no network dependency in Phase 1."""

    def generate(self, prompt: str) -> str:
        raise NotImplementedError("vLLM adapter is planned for a later phase")

from abc import ABC, abstractmethod


class TranslationProvider(ABC):
    provider_name: str

    @abstractmethod
    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def batch_translate_text(
        self,
        texts: list[str],
        source_language: str,
        target_language: str,
    ) -> list[str]:
        """批量翻译多条文本，返回与输入顺序一致的译文列表。

        单次 API 请求完成全部翻译，减少网络往返和 token 消耗。
        """
        raise NotImplementedError

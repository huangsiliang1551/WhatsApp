from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import H5Language, H5Translation


class H5LanguageService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_languages(self) -> list[H5Language]:
        """列出所有语言（默认语言排前）"""
        return list(
            self._session.scalars(
                select(H5Language).order_by(H5Language.is_default.desc(), H5Language.display_name)
            ).all()
        )

    def create_language(
        self,
        language_code: str,
        display_name: str,
        flag_emoji: str | None = None,
    ) -> H5Language:
        """创建新语言"""
        lang = H5Language(
            id=str(uuid4()),
            language_code=language_code,
            display_name=display_name,
            flag_emoji=flag_emoji,
        )
        self._session.add(lang)
        self._session.commit()
        return lang

    def update_language(self, language_id: str, **kwargs: object) -> H5Language:
        """更新语言字段"""
        lang = self._session.get(H5Language, language_id)
        if not lang:
            raise LookupError(f"Language '{language_id}' not found.")
        for key, value in kwargs.items():
            if hasattr(lang, key):
                setattr(lang, key, value)
        self._session.commit()
        return lang

    def delete_language(self, language_id: str) -> None:
        """删除语言（检查是否被翻译引用）"""
        lang = self._session.get(H5Language, language_id)
        if not lang:
            raise LookupError(f"Language '{language_id}' not found.")
        count = self._session.scalar(
            select(func.count(H5Translation.id)).where(
                H5Translation.language_code == lang.language_code
            )
        ) or 0
        if count > 0:
            raise ValueError(
                f"Cannot delete language '{lang.display_name}': {count} translations exist."
            )
        self._session.delete(lang)
        self._session.commit()

    def set_default_language(self, language_id: str) -> None:
        """设置默认语言"""
        self._session.execute(update(H5Language).values(is_default=False))
        lang = self._session.get(H5Language, language_id)
        if not lang:
            raise LookupError(f"Language '{language_id}' not found.")
        lang.is_default = True
        self._session.commit()

from __future__ import annotations

from decimal import Decimal


TWOPLACES = Decimal("0.01")


class TaskAmountAllocationService:
    @classmethod
    def allocate(
        cls,
        *,
        mode: str,
        package_count: int,
        day_total_amount: Decimal,
        manual_amounts: list[Decimal] | None = None,
    ) -> list[Decimal]:
        normalized_total = cls._quantize(day_total_amount)
        cls._validate_package_count(package_count)
        if normalized_total <= Decimal("0.00"):
            raise ValueError("day_total_amount must be positive.")

        if mode == "average":
            return cls._allocate_average(package_count=package_count, day_total_amount=normalized_total)
        if mode == "incremental":
            return cls._allocate_incremental(package_count=package_count, day_total_amount=normalized_total)
        if mode == "manual":
            return cls._allocate_manual(
                package_count=package_count,
                day_total_amount=normalized_total,
                manual_amounts=manual_amounts or [],
            )
        raise ValueError(f"Unsupported allocation mode '{mode}'.")

    @classmethod
    def _allocate_average(cls, *, package_count: int, day_total_amount: Decimal) -> list[Decimal]:
        base_amount = cls._quantize(day_total_amount / Decimal(package_count))
        amounts = [base_amount for _ in range(package_count)]
        return cls._apply_remainder(amounts=amounts, target_total=day_total_amount)

    @classmethod
    def _allocate_incremental(cls, *, package_count: int, day_total_amount: Decimal) -> list[Decimal]:
        weight_total = sum(range(1, package_count + 1))
        amounts = [
            cls._quantize(day_total_amount * Decimal(weight) / Decimal(weight_total))
            for weight in range(1, package_count + 1)
        ]
        return cls._apply_remainder(amounts=amounts, target_total=day_total_amount)

    @classmethod
    def _allocate_manual(
        cls,
        *,
        package_count: int,
        day_total_amount: Decimal,
        manual_amounts: list[Decimal],
    ) -> list[Decimal]:
        if len(manual_amounts) != package_count:
            raise ValueError("manual_amounts length must match package_count.")
        normalized_amounts = [cls._quantize(amount) for amount in manual_amounts]
        if any(amount <= Decimal("0.00") for amount in normalized_amounts):
            raise ValueError("manual amounts must be positive.")
        if sum(normalized_amounts, Decimal("0.00")) != day_total_amount:
            raise ValueError("manual amounts must sum to day_total_amount.")
        return normalized_amounts

    @classmethod
    def _apply_remainder(cls, *, amounts: list[Decimal], target_total: Decimal) -> list[Decimal]:
        current_total = sum(amounts, Decimal("0.00"))
        remainder = cls._quantize(target_total - current_total)
        if remainder == Decimal("0.00"):
            return amounts
        amounts[-1] = cls._quantize(amounts[-1] + remainder)
        return amounts

    @staticmethod
    def _validate_package_count(package_count: int) -> None:
        if package_count <= 0:
            raise ValueError("package_count must be positive.")

    @staticmethod
    def _quantize(value: Decimal) -> Decimal:
        return Decimal(value).quantize(TWOPLACES)

from dataclasses import dataclass
from decimal import Decimal


class SponsorProviderError(Exception):
    pass


@dataclass(frozen=True)
class SponsorTask:
    """Единый вид спонсорской задачи независимо от того, какая сеть её отдала.

    price=None означает, что сеть не сообщает цену за задачу в своём API (так у Tgrass) —
    фильтр "мин. цена" бота к такой задаче применить нельзя, она проходит без фильтрации.
    """

    provider: str
    task_id: str
    title: str
    link: str
    price: Decimal | None
    task_type: str

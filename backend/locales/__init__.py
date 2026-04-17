"""Per-locale string catalogs for ``i18n.t()``."""

from .en import STRINGS as EN_STRINGS
from .gu import STRINGS as GU_STRINGS
from .hi import STRINGS as HI_STRINGS

LOCALE_STRINGS = {
    "en": EN_STRINGS,
    "hi": HI_STRINGS,
    "gu": GU_STRINGS,
}

__all__ = ["LOCALE_STRINGS"]

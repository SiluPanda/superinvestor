from __future__ import annotations

from superinvestor.models.enums import AnalystRole

from .fundamental import SYSTEM_PROMPT as FUNDAMENTAL_PROMPT
from .sentiment import SYSTEM_PROMPT as SENTIMENT_PROMPT
from .synthesizer import SYSTEM_PROMPT as SYNTHESIZER_PROMPT
from .technical import SYSTEM_PROMPT as TECHNICAL_PROMPT

ANALYST_PROMPTS: dict[AnalystRole, str] = {
    AnalystRole.FUNDAMENTAL: FUNDAMENTAL_PROMPT,
    AnalystRole.TECHNICAL: TECHNICAL_PROMPT,
    AnalystRole.SENTIMENT: SENTIMENT_PROMPT,
    AnalystRole.SYNTHESIZER: SYNTHESIZER_PROMPT,
}

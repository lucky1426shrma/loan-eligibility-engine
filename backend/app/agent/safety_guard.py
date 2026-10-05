from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


class SafetyTriage:
    """
    Healthcare-grade Safety & Intent Interceptor.
    Evaluates caller utterances across all turns for:
    1. Critical medical emergencies (clinical_urgent) - THE ONE HARD RULE.
    2. Receptionist clinical advice boundaries (medical_advice).
    3. Adversarial / Prompt injection attacks (refused).
    4. Third-party unauthorized record manipulation (not_authorised).
    5. Empty or abandoned calls (abandoned).
    """

    # 1. Immediate Medical Emergencies (clinical_urgent)
    CLINICAL_URGENT_PATTERNS = [
        # Chest pain, heart symptoms
        r"\b(seene\s+mein\s+dard|seene\s+me\s+dard|chaati\s+mein\s+dard|chest\s+pain|heart\s+attack|pain\s+in\s+chest|pressure\s+in\s+chest)\b",
        # Dyspnea / breathing distress
        r"\b(saans\s+phool\s+rahi|saans\s+lene\s+mein\s+takleef|saans\s+ruk\s+rahi|difficulty\s+breathing|shortness\s+of\s+breath|cannot\s+breathe|gasping)\b",
        # Stroke / numbness
        r"\b(stroke|paralysis|face\s+droop|slurred\s+speech|left\s+arm\s+(is\s+)?numb|jaw\s+hurts|body\s+sunn)\b",
        # Bleeding / trauma
        r"\b(khoon\s+beh\s+raha|heavy\s+bleeding|severe\s+bleeding|profuse\s+bleeding|head\s+trauma|sar\s+fat\s+gaya)\b",
        # Loss of consciousness / collapse
        r"\b(behosh|unconscious|passed\s+out|collapsed|fainted|loss\s+of\s+consciousness)\b",
        # Anaphylaxis / severe acute reaction
        r"\b(anaphylaxis|throat\s+closing|gala\s+band\s+ho\s+raha|choking)\b",
        # Poisoning / overdose
        r"\b(poison|zeher|overdose|swallowed\s+chemical)\b",
        # Convulsions / seizures
        r"\b(seizure|convulsion|daura\s+pad\s+gaya|fits)\b",
    ]

    # 2. Requests for Clinical Judgement (medical_advice)
    MEDICAL_ADVICE_PATTERNS = [
        r"\b(ek\s+aur\s+goli\s+le\s+lu|goli\s+le\s+lu|dawai\s+lu\s+ya\s+nahi|dawa\s+lu\s+ya\s+nahi)\b",
        r"\b(kitni\s+der\s+mein\s+utar\s+jana\s+chahiye|kitne\s+din\s+mein\s+theek\s+hoga)\b",
        r"\b(should\s+i\s+take\s+(another|this|a)\s+pill|should\s+i\s+take\s+(the\s+)?medicine)\b",
        r"\b(can\s+i\s+stop\s+taking|is\s+this\s+dose\s+safe|how\s+many\s+tablets)\b",
        r"\b(crocin\s+le\s+raha\s+hoon|paracetamol\s+le\s+raha)\b",
        r"\b(ye\s+dawai\s+lun\s+ya\s+nahi|ye\s+tablet\s+theek\s+rahegi)\b",
        r"\b(hives|rash.*band\s+kar\s+doo|dawai\s+se\s+rash|allergic\s+reaction.*stop)\b",
    ]

    # 3. Prompt Injection / Administrator Override Patterns (refused)
    PROMPT_INJECTION_PATTERNS = [
        r"\bignore\s+(all\s+)?(your\s+)?previous\s+instructions\b",
        r"\byou\s+are\s+now\s+in\s+(administrator|developer|root|debug|maintenance)\s+mode\b",
        r"\bsystem\s+override\b",
        r"\bcancel\s+every\s+appointment\b",
        r"\bcancel\s+all\s+appointments\b",
        r"\bdelete\s+all\s+records\b",
        r"\bauthorised\s+internal\s+test\b",
        r"\brepeat\s+your\s+system\s+prompt\b",
        r"\bdump\s+(the\s+)?database\b",
        r"\b(print|dump|extract|show|list)\s+(all\s+)?(internal\s+)?(clinic\s+)?patient\s+records\b",
        r"\bprint\s+system\s+instructions\b",
        r"\baudit.*system\s+prompt\b",
    ]

    # 4. Third-party Unauthorized Action Patterns (not_authorised)
    UNAUTHORIZED_PATTERNS = [
        r"\b(padosi\s+hoon|neighbour\s+hoon|neighbor|colleague\s+hoon|friend\s+hoon)\b",
        r"\b(unka\s+number\s+mere\s+paas\s+nahi\s+hai|don't\s+have\s+their\s+number|not\s+their\s+guardian)\b",
    ]

    @classmethod
    def check_clinical_urgent(cls, text: str) -> Optional[str]:
        """Check for life-threatening or urgent symptoms needing an immediate clinician."""
        for pattern in cls.CLINICAL_URGENT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"Caller reports urgent symptom: '{match.group(0)}'"
        return None

    @classmethod
    def check_medical_advice(cls, text: str) -> Optional[str]:
        """Check if caller asks receptionist for clinical judgement or drug dosage."""
        for pattern in cls.MEDICAL_ADVICE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"Caller asked for clinical advice/dosage: '{match.group(0)}'"
        return None

    @classmethod
    def check_prompt_injection(cls, text: str) -> bool:
        """Detect prompt injection and administrative mode manipulation."""
        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @classmethod
    def check_unauthorized_third_party(cls, text: str) -> Optional[str]:
        """Detect third-party actions where caller is neighbor/friend without authorization."""
        for pattern in cls.UNAUTHORIZED_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"Unauthorized third-party action detected: '{match.group(0)}'"
        return None

    @classmethod
    def is_empty_or_meaningless(cls, turns: List[str]) -> bool:
        """Check if conversation contains no actionable substance."""
        combined = " ".join(turns).strip()
        meaningless_tokens = {"hello", "haan", "ji", "arre", "theek", "hai", "background", "noise", "yes", "ok", "um"}
        words = set(re.findall(r"\b\w+\b", combined.lower()))
        return words.issubset(meaningless_tokens) or len(words) == 0

import re
from typing import List, Optional
from pydantic import BaseModel
from src.policy.models import AccountPolicy

class RuleResult(BaseModel):
    """Data model representing the results of a zero-token rule validation check."""
    passed: bool
    violations: List[str]       # Human-readable Vietnamese explanations of violations
    violation_codes: List[str] # Technical error codes (e.g. LENGTH_TOO_SHORT, BANNED_WORD_PRESENT)

class RuleCritic:
    """Validator class that evaluates draft posts against the hard constraints of an AccountPolicy without using AI tokens."""
    def __init__(self, policy: AccountPolicy):
        self.policy = policy
        self.min_length: Optional[int] = None
        self.max_length: Optional[int] = None
        self.min_hashtags: Optional[int] = None
        self.max_hashtags: Optional[int] = None
        self.max_emojis: Optional[int] = None
        self.banned_words: List[str] = []
        self.disallow_links: bool = False
        
        self._parse_constraints()

    def _parse_constraints(self):
        """Helper to parse raw markdown constraints list into structured evaluation fields using regex."""
        for constraint in self.policy.constraints:
            # 1. Parse Length Constraints
            # Match "between X and Y characters"
            len_between_match = re.search(r"between\s+(\d+)\s+and\s+(\d+)\s+characters", constraint, re.IGNORECASE)
            if len_between_match:
                self.min_length = int(len_between_match.group(1))
                self.max_length = int(len_between_match.group(2))
                continue
            
            # Match "strictly under X characters" (e.g., under 280)
            len_under_match = re.search(r"under\s+(\d+)\s+characters", constraint, re.IGNORECASE)
            if len_under_match:
                # strictly under X means <= X - 1
                self.max_length = int(len_under_match.group(1)) - 1
                self.min_length = 0
                continue

            # 2. Parse Hashtag Constraints
            # Match "more than X hashtags" or "maximum of X hashtags"
            max_hash_match = re.search(r"(?:more\s+than|maximum\s+of)\s+(\d+)\s+hashtag", constraint, re.IGNORECASE)
            if max_hash_match:
                self.max_hashtags = int(max_hash_match.group(1))
                continue
                
            # Match "exactly X relevant hashtag"
            exact_hash_match = re.search(r"exactly\s+(\d+)\s+(?:relevant\s+)?hashtag", constraint, re.IGNORECASE)
            if exact_hash_match:
                self.min_hashtags = int(exact_hash_match.group(1))
                self.max_hashtags = int(exact_hash_match.group(1))
                continue

            # Match "do not use hashtags"
            if re.search(r"do\s+not\s+use\s+hashtags", constraint, re.IGNORECASE):
                self.max_hashtags = 0
                continue

            # 3. Parse Emoji Constraints
            # Match "maximum X emoji"
            emoji_match = re.search(r"maximum\s+(\d+)\s+emoji", constraint, re.IGNORECASE)
            if emoji_match:
                self.max_emojis = int(emoji_match.group(1))
                continue

            # 4. Parse Link Constraints
            # Match "do not include promotional links", "no links", "avoid links", etc.
            if re.search(r"links\b", constraint, re.IGNORECASE) and re.search(r"(?:do not|no|avoid|never)\b", constraint, re.IGNORECASE):
                self.disallow_links = True

            # 5. Parse Banned Words
            # Check if constraint mentions terms like buzzword, banned, avoid, never use
            if any(kw in constraint.lower() for kw in ["buzzword", "banned", "avoid", "never use", "no promotional"]):
                # Extract double-quoted words (e.g. "synergy")
                quoted_words = re.findall(r'"([^"]+)"', constraint)
                if not quoted_words:
                    # Extract single-quoted words (e.g. 'synergy')
                    quoted_words = re.findall(r"'([^']+)'", constraint)
                if quoted_words:
                    self.banned_words.extend([w.strip() for w in quoted_words if w.strip()])

    def check(self, post: str) -> RuleResult:
        """Evaluates the draft post content against parsed rules.

        Returns a RuleResult containing pass status and a list of violations.
        """
        violations = []
        violation_codes = []

        # 1. Length check
        post_length = len(post)
        if self.min_length is not None and post_length < self.min_length:
            violations.append(f"Nội dung quá ngắn ({post_length} ký tự, yêu cầu tối thiểu {self.min_length} ký tự).")
            violation_codes.append("LENGTH_TOO_SHORT")
        
        if self.max_length is not None and post_length > self.max_length:
            violations.append(f"Nội dung quá dài ({post_length} ký tự, yêu cầu tối đa {self.max_length} ký tự).")
            violation_codes.append("LENGTH_TOO_LONG")

        # 2. Banned words check (whole word match using word boundaries, case-insensitive)
        for word in self.banned_words:
            pattern = r"\b" + re.escape(word) + r"\b"
            if re.search(pattern, post, re.IGNORECASE):
                violations.append(f"Bài viết chứa từ bị cấm: '{word}'.")
                violation_codes.append("BANNED_WORD_PRESENT")

        # 3. Hashtags check
        # Match hashtags starting with '#' followed by letters, numbers, or underscores
        hashtags = re.findall(r"#\w+", post)
        hashtag_count = len(hashtags)

        if self.max_hashtags is not None and hashtag_count > self.max_hashtags:
            violations.append(f"Bài viết chứa quá nhiều hashtag ({hashtag_count} hashtags, yêu cầu tối đa: {self.max_hashtags}).")
            violation_codes.append("TOO_MANY_HASHTAGS")

        if self.min_hashtags is not None and hashtag_count < self.min_hashtags:
            violations.append(f"Bài viết chứa quá ít hashtag ({hashtag_count} hashtags, yêu cầu tối thiểu: {self.min_hashtags}).")
            violation_codes.append("TOO_FEW_HASHTAGS")

        # 4. Emoji check
        # Matches emoji range characters. BMP characters (like Vietnamese letters) will not be false-matched.
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff]|\u2600-\u27bf",
            flags=re.UNICODE
        )
        emojis = emoji_pattern.findall(post)
        emoji_count = len(emojis)

        if self.max_emojis is not None and emoji_count > self.max_emojis:
            violations.append(f"Bài viết chứa quá nhiều emoji ({emoji_count} emoji, yêu cầu tối đa: {self.max_emojis}).")
            violation_codes.append("TOO_MANY_EMOJIS")

        # 5. Links/URL check
        if self.disallow_links:
            link_pattern = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
            links = link_pattern.findall(post)
            if links:
                violations.append(f"Bài viết chứa liên kết/link (không được phép): '{links[0]}'.")
                violation_codes.append("LINKS_NOT_ALLOWED")

        passed = len(violations) == 0
        return RuleResult(
            passed=passed,
            violations=violations,
            violation_codes=violation_codes
        )

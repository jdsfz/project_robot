"""Shared movement calculation: outputs wheel speeds from -100 to 100."""


def wheel_speeds(keys: set[str]) -> tuple[int, int]:
    if ("w" in keys) == ("s" in keys):
        return 0, 0
    direction = 1 if "w" in keys else -1
    left = right = direction * 40
    if "a" in keys and "d" not in keys:
        right = int(right * 1.3)
    elif "d" in keys and "a" not in keys:
        left = int(left * 1.3)
    return max(-100, min(100, left)), max(-100, min(100, right))

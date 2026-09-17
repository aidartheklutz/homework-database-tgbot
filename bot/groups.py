SEST1 = "SEST-1-25"
SEST2 = "SEST-2-25"
GROUPS = (SEST1, SEST2)


def is_valid_group(group_name: str | None) -> bool:
    return group_name in GROUPS

"""Optional event extension: emit once at the top of each hour."""
API_VERSION = 1
_last = None


def poll(config, now):
    global _last
    token = now.strftime("%Y-%m-%d %H")
    if now.minute == 0 and token != _last:
        _last = token
        return True
    return False


def register(registry):
    registry.register_event("hourly_chime", "整点报时（扩展）", poll)

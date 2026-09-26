class UnidenError(Exception):
    pass


class UnidenOutOfResourcesError(UnidenError):
    def __init__(self, s="Out of resources"):
        return UnidenError.__init__(self, s)


class UnidenValueError(UnidenError):
    def __init__(self, s="Command format error / Value error"):
        return UnidenError.__init__(self, s)


class UnidenSyncError(UnidenError):
    def __init__(self, s="The command is invalid at the time"):
        return UnidenError.__init__(self, s)


class UnidenFramingError(UnidenError):
    def __init__(self, s="Framing error"):
        return UnidenError.__init__(self, s)


class UnidenOverrunError(UnidenError):
    def __init__(self, s="Overrun error"):
        return UnidenError.__init__(self, s)


class UnidenUnexpectedResponseError(UnidenError):
    def __init__(self, s="Unexpected response"):
        return UnidenError.__init__(self, s)




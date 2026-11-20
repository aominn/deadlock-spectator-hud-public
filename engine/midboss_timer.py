"""Validated next-spawn deadlines on the native match clock."""
from bisect import bisect_right
from math import ceil, isfinite


class MidbossTimeline:
    def __init__(self, data):
        self.updates = ()
        self.seconds = ()
        if not isinstance(data, dict) or data.get('schema') != 1:
            return
        rows = data.get('updates')
        if not isinstance(rows, list) or len(rows) > 256:
            return

        last = -1
        for row in rows:
            if not isinstance(row, list) or len(row) != 2:
                return
            second, deadline = row
            if type(second) is not int or not last < second <= 21600:
                return
            if type(deadline) not in (int, float) or not (
                deadline == 0 or second - 1 < deadline <= second + 3600
            ) or not isfinite(deadline):
                return
            last = second

        self.updates = tuple((second, deadline) for second, deadline in rows)
        self.seconds = tuple(second for second, _ in self.updates)

    def remaining(self, second):
        if type(second) is not int or second < 0:
            return None
        index = bisect_right(self.seconds, second) - 1
        if index < 0:
            return None
        remaining = ceil(self.updates[index][1] - second)
        return remaining if remaining > 0 else None

# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import os
import re


# See https://www.kernel.org/doc/Documentation/filesystems/proc.txt
_PROC_PID_MOUNTINFO_LINE = re.compile(
        '^(?P<mount_id>[0-9]+) '
        '(?P<parent_id>[0-9]+) '
        '(?P<major>[0-9]+):(?P<minor>[0-9]+) '
        '(?P<root>/[^ ]*) '
        '(?P<mount>/[^ ]*) '  # Spaces are encoded as "\040"
        '.+$')


class MountFinder(object):
    def __init__(self):
        self._mount_points = []

    def load(self, filename=None):
        if filename is None:
            filename = '/proc/%d/mountinfo' % os.getpid()

        f = open(filename)
        for l in f:
            line = l.rstrip()
            m = _PROC_PID_MOUNTINFO_LINE.match(line)
            self._mount_points.append(m.groupdict()['mount'])
        f.close()

    def _normpath_no_trailing_slash(self, abs_path):
        return os.path.normpath(abs_path)

    def _normpath_trailing_slash(self, abs_path):
        return os.path.join(os.path.normpath(abs_path), '')

    def below(self, abs_path, inclusive=False):
        prefix = self._normpath_trailing_slash(abs_path)
        for abs_candidate in self._mount_points:
            normed_candidate = self._normpath_trailing_slash(abs_candidate)
            if normed_candidate.startswith(prefix):
                if normed_candidate == prefix and not inclusive:
                    continue
                yield self._normpath_no_trailing_slash(normed_candidate)

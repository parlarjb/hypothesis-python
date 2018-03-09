# coding=utf-8
#
# This file is part of Hypothesis, which may be found at
# https://github.com/HypothesisWorks/hypothesis-python
#
# Most of this work is copyright (C) 2013-2018 David R. MacIver
# (david@drmaciver.com), but it contains contributions by others. See
# CONTRIBUTING.rst for a full list of people who may hold copyright, and
# consult the git log if you need to determine who owns an individual
# contribution.
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.
#
# END HEADER

from __future__ import division, print_function, absolute_import

from random import Random
from itertools import islice


class RandomWithSeed(Random):
    """A subclass of Random designed to expose the seed it was initially
    provided with.

    We consistently use this instead of Random objects because it makes
    examples much easier to recreate.
    """

    def __init__(self, seed):
        super(RandomWithSeed, self).__init__(seed)
        self.seed = seed

    def __copy__(self):
        result = RandomWithSeed(self.seed)
        result.setstate(self.getstate())
        return result

    def __deepcopy__(self, table):
        return self.__copy__()

    def __repr__(self):
        return u'RandomWithSeed(%s)' % (self.seed,)

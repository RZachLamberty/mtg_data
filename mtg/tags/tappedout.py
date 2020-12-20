#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: tappedout
Created: 2019-07-28

Description:

    acquiring and aliasing the tags I've used in the past on tappedout

    over time, I want these to converge towards official tags

Usage:

    >>> import mtg.tags.tappedout

"""

import logging as _logging

from mtg.extract.tappedout import (TAPPEDOUT_SPECIAL_TAGS as
                                   _TAPPEDOUT_SPECIAL_TAGS,
                                   build_categories_df as _build_categories_df,
                                   get_all_categories as _get_all_categories)
from mtg.load.neo import NeoNode, NeoConstraint, NeoRelationship
from mtg.tags import Tags as _Tags

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

_LOGGER = _logging.getLogger(__name__)
_LOGGER.setLevel(_logging.DEBUG)


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

class TappedoutTags(_Tags):
    def __init__(self, db_conf, id_attribute='name', tappedout_owner='ndlambo'):
        super().__init__(db_conf=db_conf,
                         tag_label='TappedoutTag',
                         id_attribute=id_attribute)

        self.tappedout_tag_df = _build_categories_df(
            _get_all_categories(owner=tappedout_owner))

    @property
    def cards(self):
        try:
            return self._cards
        except AttributeError:
            _LOGGER.debug("building neo card node list")
            self._cards = [NeoNode(name=name, label='Card')
                           for name in self.tappedout_tag_df.card.unique()]
            return self._cards

    @property
    def tags(self):
        try:
            return self._tags
        except AttributeError:
            _LOGGER.debug("building neo tag node list")
            self._tags = [NeoNode(name=tag, label=self.tag_label)
                          for tag in (set(self.tappedout_tag_df
                                          .tappedout_tag
                                          .unique())
                                      .difference(_TAPPEDOUT_SPECIAL_TAGS))]
            return self._tags

    @property
    def constraints(self):
        return [NeoConstraint('Card', 'name'),
                NeoConstraint(self.tag_label, 'Name')]

    @property
    def card_tags(self):
        try:
            return self._card_tags
        except AttributeError:
            self._card_tags = [
                NeoRelationship(src=NeoNode(name=card, label='Card'),
                                dst=NeoNode(name=tag, label=self.tag_label),
                                _type='HAS_TAG')
                for (card, tag) in (self.tappedout_tag_df
                                    [['card', 'tappedout_tag']]
                                    .values)
                if tag not in _TAPPEDOUT_SPECIAL_TAGS]
            return self._card_tags

    @property
    def tag_hierarchy(self):
        # eventually this might get hard-coded but for now ignore it
        return []
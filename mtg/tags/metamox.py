#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: metamox.py
Author: zlamberty
Created: 2018-06-25

Description:
    utilities for scraping information off of the awesome metamox.com site

Usage:

    >>> import mtg.tags.metamox


"""

import logging as _logging

from mtg.extract.metamox import get_all_tags as _get_all_tags
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

class MetamoxTags(_Tags):
    def __init__(self, db_conf, id_attribute='name'):
        super().__init__(db_conf=db_conf,
                         tag_label='MetamoxTag',
                         id_attribute=id_attribute)

        self.metamox_tag_df = _get_all_tags().drop(columns='index')

    @property
    def cards(self):
        try:
            return self._cards
        except AttributeError:
            _LOGGER.debug("building neo card node list")
            self._cards = [NeoNode(name=name, label='Card')
                           for name in self.metamox_tag_df.name.unique()]
            return self._cards

    @property
    def tags(self):
        try:
            return self._tags
        except AttributeError:
            _LOGGER.debug("building neo tag node list")
            tags = {tag
                    for tag_key in ['tag', 'subtag']
                    for tag in self.metamox_tag_df[tag_key].unique()}
            tags.discard(None)
            self._tags = [NeoNode(name=tag, label=self.tag_label) for tag in tags]
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
            self._card_tags = []
            for tag_key in ['tag', 'subtag']:
                idx_non_null = self.metamox_tag_df[tag_key].notnull()
                df = self.metamox_tag_df[idx_non_null][['name', tag_key]]

                self._card_tags += [
                    NeoRelationship(src=NeoNode(name=name, label='Card'),
                                    dst=NeoNode(name=tag, label=self.tag_label),
                                    _type='HAS_TAG')
                    for (name, tag) in df.values]
            return self._card_tags

    @property
    def tag_hierarchy(self):
        try:
            return self._tag_hierarchy
        except AttributeError:
            tag_rels = (self.metamox_tag_df
                        [self.metamox_tag_df.subtag.notnull()]
                        [['subtag', 'tag']]
                        .sort_values(['subtag', 'tag'])
                        .drop_duplicates())
            self._tag_hierarchy = [
                NeoRelationship(src=NeoNode(name=subtag, label=self.tag_label),
                                dst=NeoNode(name=tag, label=self.tag_label),
                                _type='IS_SUBTAG_OF')
                for subtag, tag in tag_rels.values]
            return self._tag_hierarchy
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: metamox.py
Author: zlamberty
Created: 2018-06-25

Description:
    utilities for scraping information off of the awesome metamox.com site

Usage:
    import metamox


"""

import logging as _logging
import re as _re
from functools import lru_cache

import lxml.html as _html
import pandas as _pd
import requests as _requests

from mtg.colors import MTG_COLORS as _MTG_COLORS
from mtg.utils import file_cache

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

_LOGGER = _logging.getLogger(__name__)
_LOGGER.setLevel(_logging.DEBUG)

COLORS = [_.fullname for _ in _MTG_COLORS]
FORMATS = ['commander', 'legacy', 'modern', 'standard', ]


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def _parse_price(px, currency_symbol='$'):
    """stolen from here: https://stackoverflow.com/questions/8421922/"""
    try:
        return float(px.strip(currency_symbol))
    except ValueError:
        return None


@lru_cache(None)
def get_tag_list():
    """hit up http://www.metamox.com/tag/ to generate a list of tags"""
    resp = _requests.get(url='http://www.metamox.com/tag/')
    root = _html.fromstring(resp.text)
    cat_xp = './/div[@class="card-block"]//div[@class="column-cell"]/a'

    # we only need top-level tags; the sub-levels appear on the pages themselves
    return [[cat_a.attrib['href'], cat_a.text] for cat_a in root.xpath(cat_xp)]


@lru_cache(None)
def get_tag(tag_url, tag_name, get_colors=False, get_legality=False):
    _LOGGER.debug('getting tag "{}" from {}'.format(tag_name, tag_url))
    resp = _requests.get(url='http://www.metamox.com/{}/'.format(tag_url),
                         cookies={'search-view': 'list'})
    root = _html.fromstring(resp.text)
    card_rows = root.xpath('.//a[contains(@class, "cardable")]')
    cards = []
    for card_row in card_rows:
        color_identity = {}
        format_legality = {}
        row_classes = set(card_row.classes)
        if get_colors:
            color_identity = {color: color in row_classes for color in COLORS}
        if get_legality:
            format_legality = {fmt: fmt in row_classes for fmt in FORMATS}

        name = card_row.find('div/div').text.strip()

        try:
            subtag_xp = './ancestor::div[1]/preceding-sibling::div//h3/text()'
            subtag = (card_row.xpath(subtag_xp)[0])
        except IndexError:
            subtag = None

        cards.append({'name': name,
                      'tag': tag_name,
                      'subtag': subtag,
                      **color_identity,
                      **format_legality, })

    keep_cols = ['name', 'tag', 'subtag']
    if get_colors:
        keep_cols += COLORS
    if get_legality:
        keep_cols += FORMATS

    if cards:
        cards = _pd.DataFrame(cards)[keep_cols]
    else:
        cards = _pd.DataFrame(columns=keep_cols)

    if get_colors:
        cards.colorless = ~cards[COLORS].any(axis=1)

    return cards


@file_cache('metamox_tags.pkl')
def get_all_tags(tag_list=None):
    tag_list = tag_list or get_tag_list()
    df = _pd.DataFrame()
    for tag in tag_list:
        tag_url = tag[0]
        tag_name = tag[1]
        df = df.append(get_tag(tag_url, tag_name), ignore_index=True)

    return df.reset_index()


def add_my_tags(df):
    """the tags and subtags we've defined here are specific to metamox.
    independently I have generated a taxonomy / tagging system for cards and I'd
    like to bring these tags into that framework, so here we normalize them all

    """
    mmtags = df[['tag', 'subtag']].drop_duplicates()

    # fixing board wipes, aka "wraths"
    # we will go with the convention "mtg:wrath:[target]:[method]"
    # complicating things: targets will be singularized, methods will have to be
    # cleaned of spaces etc
    tm = (mmtags
          [mmtags.tag == 'board-wipes']
          .subtag
          .str.lower()
          .str.extract(r'(?P<target>\w+) - mass (?P<method>\w+)')
          .dropna())
    tm.target = (tm
                 .target
                 .str.replace('ies$', 'y')
                 .str.replace('s$', ''))
    tm.loc[:, 'my_tag'] = 'mtg:wrath:' + tm.target + ':' + tm.method
    mmtags = mmtags.join(tm[['my_tag']])

    # copy, aka "clone"
    # a lot of leeway here. we'll go with "mtg:clone:[target]"
    # there is one special record -- the "Sprouter" subtag. this is a copy of
    # the self, so we'll call the target "self"
    copy_targets = (mmtags
                    [mmtags.tag == 'copy']
                    .subtag
                    .str.lower()
                    .str.extract(r'(?:copy )?(?P<target>[\w\s]+)')
                    .target
                    .str.replace(' ', '_')
                    .replace({'sprouter': 'self'}))
    mmtags.loc[copy_targets.index, 'my_tag'] = 'mtg:clone:' + copy_targets

    # counters
    # several categories here:
    #   counter + [...] -- mtg:counter:then:[dowhat]
    #   counter [target] -- mtg:counter:target:[target]
    #   [modifier] counter -- mtg:counter:[modifier]
    #   general mapping (stuff that doesn't fall into the above buckets)
    ctrs = mmtags[mmtags.tag == 'counters']

    def f_counter(subtag):
        subtag = subtag.lower()

        # special general remappings
        if subtag == 'auto-counter':
            return 'mtg:counter:automatically'

        if subtag == 'stopping counters':
            return 'mtg:cant_counter:'

        try:
            return 'mtg:counter:then:{}'.format(
                _re.findall(r'.* \+ ([\w\s]+)', subtag)[0])
        except IndexError:
            pass

        try:
            target = _re.findall(r'counter ([\w\s]+)', subtag)[0]
            target = _re.sub('ies$', 'y', target)
            target = _re.sub('s$', '', target)
            target = _re.sub(' ', '_', target)
            return 'mtg:counter:target:{}'.format(target)
        except IndexError:
            pass

        try:
            modifier = _re.findall(r'([\w\s]+) counter$', subtag)[0]
            modifier = _re.sub(' ', '_', modifier)
            return 'mtg:counter:{}'.format(modifier)
        except IndexError:
            pass

    mmtags.loc[ctrs.index, 'my_tag'] = ctrs.subtag.str.lower().apply(f_counter)

    # devotion
    # let's tag color when provided as 'mtg:devotion:[color]'
    # we'll tag amount as 'mtg:devotion:amount:[amount]'
    # and devotion matters gets a different value
    devotion = mmtags[mmtags.tag == 'devotion']
    devotion_colors = (devotion.subtag
                       .str.lower()
                       .str.extract('(?P<my_tag>[a-z]+) devotion')
                       .dropna())
    mmtags.loc[devotion_colors.index, 'my_tag'] = (
            'mtg:devotion:color:' + devotion_colors.my_tag)
    mmtags.loc[
        mmtags.subtag == 'Devotion Matters',
        'my_tag'
    ] = 'mtg:devotion_matters'

    return mmtags

# todo: clean up storm (and probably other keyword) tags where the presence
#  of the word in the name of a card is sufficient for tagging

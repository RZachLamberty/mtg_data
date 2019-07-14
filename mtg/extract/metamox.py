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

import locale
import logging
import re

import lxml.html
import pandas as pd
import requests

from mtg.colors import MTG_COLORS

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

# just setting price defaults, could have hardcoded, '$', probably should have..
locale.setlocale(locale.LC_ALL, 'en_US.UTF8')

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

TAG_LIST = ['board-wipes',
            'copy',
            'counters',
            'devotion',
            'extras',
            'hate',
            'lands',
            'mana-rocks',
            'mass-haste',
            'reanimate',
            'removal',
            'theft',
            'tutors', ]
COLORS = [_.fullname for _ in MTG_COLORS]
FORMATS = ['commander', 'legacy', 'modern', 'standard', ]


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def _parse_price(px):
    """stolen from here: https://stackoverflow.com/questions/8421922/"""
    try:
        return locale.atof(px.strip(locale.localeconv()['currency_symbol']))
    except ValueError:
        return None


def get_tag(tag):
    resp = requests.get(url='http://www.metamox.com/tag/{}/'.format(tag),
                        cookies={'search-view': 'list'})
    root = lxml.html.fromstring(resp.text)
    card_rows = root.xpath('.//tr[contains(@class, "card ")]')
    cards = []
    for card_row in card_rows:
        row_classes = set(card_row.classes)
        color_identity = {color: color in row_classes for color in COLORS}
        format_legality = {fmt: fmt in row_classes for fmt in FORMATS}
        name = card_row.find('./td/a').text
        LOGGER.debug('parsing card {}'.format(name))
        rarity = card_row.xpath('.//*[contains(@class, "hidden-sm")]')[0].text
        price = _parse_price(card_row.find('./td/span').text)
        try:
            subtag_xp = './ancestor::table/preceding-sibling::h2[1]'
            subtag = (card_row.xpath(subtag_xp)[0])
            subtag = subtag.text
        except IndexError:
            subtag = None
        cards.append({'name': name,
                      'rarity': rarity,
                      'price': price,
                      'tag': tag,
                      'subtag': subtag,
                      **color_identity,
                      **format_legality, })

    keep_cols = ['name', 'price', 'rarity', 'tag', 'subtag'] + COLORS + FORMATS
    cards = pd.DataFrame(cards)[keep_cols]
    cards.colorless = ~cards[COLORS].any(axis=1)

    return cards


def get_all_tags(tag_list=None):
    tag_list = tag_list or TAG_LIST
    df = pd.DataFrame()
    for tag in tag_list:
        LOGGER.debug(tag)
        df = df.append(get_tag(tag), ignore_index=True)

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
                re.findall(r'.* \+ ([\w\s]+)', subtag)[0])
        except IndexError:
            pass

        try:
            target = re.findall(r'counter ([\w\s]+)', subtag)[0]
            target = re.sub('ies$', 'y', target)
            target = re.sub('s$', '', target)
            target = re.sub(' ', '_', target)
            return 'mtg:counter:target:{}'.format(target)
        except IndexError:
            pass

        try:
            modifier = re.findall(r'([\w\s]+) counter$', subtag)[0]
            modifier = re.sub(' ', '_', modifier)
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

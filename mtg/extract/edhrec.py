#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: edhrec.py
Author: zlamberty
Created: 2018-04-27

Description:
    for scraping out edh recommendation information from the edhrec.com website

Usage:
    > import edhrec
    > edhrec.commanders_and_cards().to_csv('edhrec.csv', index=False)

"""

import json
import logging
import os

import lxml.html
import pandas as pd
import requests

from mtg import colors

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

LOGGER = logging.getLogger(__name__)

logging.getLogger('urllib3').setLevel(logging.WARNING)

EDH_REC_URL = 'https://edhrec.com/commanders'

HERE = os.path.dirname(os.path.realpath(__file__))
F_EDHREC_CACHE = os.path.join(HERE, 'edhrec.csv')


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def get_commanders(baseurl=EDH_REC_URL):
    LOGGER.debug('getting commander summary info')

    def make_url(color_combo):
        return '{}/{}'.format(baseurl, ''.join(color_combo))

    df = (pd.concat(objs=[_parse_edhrec_cardlist(url=make_url(color_combo),
                                                 # for partner commanders:
                                                 include_multicards=True)
                          for color_combo
                          in colors.ALL_COLOR_COMBOS_W_COLORLESS],
                    ignore_index=True)
          .reset_index(drop=True))

    # this will pull in commanders as well as staples. subset to commanders only
    df = df[df.cardlist_tag.str.contains('commander')]
    df.loc[:, 'num_decks'] = (df
                              .label
                              .str.extract('(\d+) decks?', expand=False)
                              .astype(int))

    return df


def get_commander_summary(commander, baseurl=EDH_REC_URL):
    LOGGER.debug('getting info for commander {}'.format(commander))
    url = '{}/{}'.format(baseurl, commander)
    return _parse_edhrec_cardlist(url)


def get_commanders_and_cards(baseurl=EDH_REC_URL, forcerefresh=False):
    # if the local cache version doesn't exist, or forcerefresh is True, go
    # download the information and save it locally. otherwise, just return the
    # cached version
    if forcerefresh or not os.path.isfile(F_EDHREC_CACHE):
        df_cmdrs = (get_commanders(baseurl)
        [['name', 'url', 'num_decks']])
        df_cmdrs.loc[:, 'commander_name'] = (df_cmdrs
                                             .url
                                             .str.extract('/commanders/(.*)',
                                                          expand=False))
        df_cmdrs.drop(['url'], axis=1, inplace=True)
        df_cmdrs.drop_duplicates(inplace=True)

        df = pd.DataFrame()
        for (fullname, num_decks, urlname) in df_cmdrs.values:
            dfnow = get_commander_summary(urlname)

            if dfnow.empty:
                continue

            dfnow = dfnow[['name']]
            dfnow.loc[:, 'commander'] = fullname
            dfnow.loc[:, 'num_decks'] = num_decks
            df = pd.concat([df, dfnow], ignore_index=True)

        df = df.reset_index(drop=True)

        df.to_csv(F_EDHREC_CACHE, index=False)

        return df
    else:
        return pd.read_csv(F_EDHREC_CACHE)


def _parse_edhrec_cardlist(url, include_multicards=False):
    resp = requests.get(url)
    root = lxml.html.fromstring(resp.text)

    # awesome dirty hack: json already built and embedded
    js = [_.text
          for _ in root.xpath('.//div[@class="container"]/script')
          if _.text and 'json_dict' in _.text][0]

    startstr = 'const json_dict = '
    assert js.startswith(startstr)
    js = js[len(startstr):-1]

    j = json.loads(js)['cardlists']

    if j is None:
        # no info, empty df is okay
        return pd.DataFrame()

    def ck_lookup(cardview, key):
        return cardview.get('cardkingdom', {}).get(key)

    def ck_card_lookup(cardview, key):
        return cardview.get('cards', [{}])[0].get(key)

    if include_multicards:
        df_smry = pd.DataFrame([{'cardlist_tag': cardlist['tag'],
                                 'url': cardview['url'],
                                 'label': cardview['label'],
                                 'name': cardview['name'],
                                 'price': ck_lookup(cardview, 'price'),
                                 'cardkingdom_url': ck_lookup(cardview, 'url'),
                                 'variation': ck_lookup(cardview, 'variation'),
                                 'is_commander': card.get('is_commander'),
                                 'is_banned': card.get('is_banned'),
                                 'is_unofficial': card.get('is_unofficial'),
                                 'image': card.get('image'), }
                                for cardlist in j
                                for cardview in cardlist['cardviews']
                                for card in cardview.get('cards', [])])
    else:
        df_smry = pd.DataFrame([{'cardlist_tag': cardlist['tag'],
                                 'url': cardview['url'],
                                 'label': cardview['label'],
                                 'name': cardview['name'],
                                 'price': ck_lookup(cardview, 'price'),
                                 'cardkingdom_url': ck_lookup(cardview, 'url'),
                                 'variation': ck_lookup(cardview, 'variation'),
                                 'is_commander': ck_card_lookup(cardview,
                                                                'is_commander'),
                                 'is_banned': ck_card_lookup(cardview,
                                                             'is_banned'),
                                 'is_unofficial': ck_card_lookup(
                                     cardview, 'is_unofficial'),
                                 'image': ck_card_lookup(cardview, 'image'), }
                                for cardlist in j
                                for cardview in cardlist['cardviews']])

    return df_smry

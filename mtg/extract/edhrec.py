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

import logging
import os

import pandas as pd
import requests
import tqdm

from mtg import colors

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

LOGGER = logging.getLogger(__name__)

logging.getLogger('urllib3').setLevel(logging.WARNING)

EDH_REC_URL = 'https://edhrec.com/commanders'
EDH_REC_S3_URL = 'https://edhrec-json.s3.amazonaws.com/en/commanders'

HERE = os.path.dirname(os.path.realpath(__file__))
F_EDHREC_CACHE = os.path.join(HERE, 'edhrec.parquet')


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def get_commanders(s3url=EDH_REC_S3_URL):
    LOGGER.debug('getting commander summary info')

    def make_url(color_combo):
        return f"{s3url}/{''.join(color_combo).lower()}.json"

    df = (pd.concat(objs=[_parse_edhrec_cardlist(url=make_url(color_combo),
                                                 # for partner commanders:
                                                 include_multicards=True)
                          for color_combo
                          in colors.ALL_COLOR_COMBOS_W_COLORLESS],
                    ignore_index=True)
          .reset_index(drop=True))

    # this will pull in commanders as well as staples. subset to commanders only
    df = df[df.is_commander]
    df.loc[:, 'num_decks'] = (df
                              .label
                              .str.extract('(\d+) decks?', expand=False)
                              .astype(int))

    return df


def get_commander_summary(commander, s3url=EDH_REC_S3_URL):
    LOGGER.debug(f'getting info for commander {commander}')
    url = f'{s3url}/{commander}.json'
    return _parse_edhrec_cardlist(url)


def get_commanders_and_cards(s3url=EDH_REC_S3_URL, forcerefresh=False):
    # if the local cache version doesn't exist, or forcerefresh is True, go
    # download the information and save it locally. otherwise, just return the
    # cached version
    if forcerefresh or not os.path.isfile(F_EDHREC_CACHE):
        df_cmdrs = get_commanders(s3url)[['name', 'url', 'num_decks']]
        df_cmdrs.loc[:, 'commander_name'] = (df_cmdrs
                                             .url
                                             .str.extract('/commanders/(.*)',
                                                          expand=False))
        df_cmdrs.drop(['url'], axis=1, inplace=True)
        df_cmdrs.drop_duplicates(inplace=True)

        df = pd.DataFrame()
        for (fullname, num_decks, urlname) in tqdm.tqdm(df_cmdrs.values):
            dfnow = get_commander_summary(urlname)

            if dfnow.empty:
                continue

            dfnow = dfnow[['name']].copy()
            dfnow.loc[:, 'commander'] = fullname
            dfnow.loc[:, 'num_decks'] = num_decks
            df = pd.concat([df, dfnow], ignore_index=True)

        df = df.reset_index(drop=True)

        df.to_parquet(F_EDHREC_CACHE, index=False)

        return df
    else:
        return pd.read_csv(F_EDHREC_CACHE)


def _parse_edhrec_cardlist(url, include_multicards=False):
    resp = requests.get(url)
    j0 = resp.json()
    cardlists = j0['container']['json_dict']['cardlists']

    if cardlists is None:
        # no info, empty df is okay
        return pd.DataFrame()

    def ck_lookup(card, key):
        try:
            return card['prices']['cardkingdom'][key]
        except KeyError:
            return None

    def img_lookup(card):
        try:
            return card['image_uris'][0]['normal']
        except TypeError:
            return card['image_uris'][0][0]
        except KeyError:
            return None

    return pd.DataFrame([{'cardlist_tag': cardlist['tag'],
                           'url': card['url'],
                           'label': card['label'],
                           'name': card['name'],
                           'price': ck_lookup(card, 'price'),
                           'cardkingdom_url': ck_lookup(card, 'url'),
                           'is_commander': card.get('is_commander'),
                           'is_banned': card.get('banned'),
                           'is_unofficial': card.get('unofficial'),
                           'image': img_lookup(card),
                           'legal_commander': card.get('legal_commander'),
                           'legal_companion': card.get('legal_companion'),
                           'legal_partner': card.get('legal_companion'), }
                          for cardlist in cardlists
                          for card in cardlist['cardviews']])


if __name__ == '__main__':
    df = get_commanders_and_cards(forcerefresh=True)
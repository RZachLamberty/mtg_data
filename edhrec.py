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

import argparse
import json
import logging
import logging.config
import os
import yaml

import lxml.html
import pandas as pd
import requests

import mtgconstants


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

HERE = os.path.dirname(os.path.realpath(__file__))
LOGGER = logging.getLogger(__name__)
LOGCONF = os.path.join(HERE, 'logging.yaml')
with open(LOGCONF, 'rb') as f:
    logging.config.dictConfig(yaml.load(f))
logging.getLogger('urllib3').setLevel(logging.WARNING)

EDH_REC_URL = 'https://edhrec.com/commanders'
F_EDHREC_CACHE = os.path.join(HERE, 'edhrec.csv')

# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def commanders(baseurl=EDH_REC_URL):
    LOGGER.debug('getting commander summary info')
    df = pd.concat(
        objs=[
            _parse_edhrec_cardlist(
                url='{}/{}'.format(baseurl, ''.join(color_combo)),
                # for partner commanders:
                include_multicards=True
            )
            for color_combo in mtgconstants.ALL_COLOR_COMBOS_W_COLORLESS
        ],
        ignore_index=True
    ).reset_index(drop=True)

    # this will pull in commanders as well as staples. subset to commanders only
    df = df[df.cardlist_tag.str.contains('commander')]
    df.loc[:, 'num_decks'] = df.label \
        .str.extract('(\d+) decks?', expand=False) \
        .astype(int)

    return df


def commander_summary(commander, baseurl=EDH_REC_URL):
    LOGGER.debug('getting info for commander {}'.format(commander))
    url = '{}/{}'.format(baseurl, commander)
    return _parse_edhrec_cardlist(url)


def commanders_and_cards(baseurl=EDH_REC_URL, forcerefresh=False):
    # if the local cache version doesn't exist, or forcerefresh is True, go
    # download the information and save it locally. otherwise, just return the
    # cached version
    if forcerefresh or not os.path.isfile(F_EDHREC_CACHE):
        df_commanders = commanders(baseurl)[['name', 'url', 'num_decks']]
        df_commanders.loc[:, 'commander_name'] = df_commanders.url.str.extract(
            '/commanders/(.*)', expand=False
        )
        df_commanders.drop(['url'], axis=1, inplace=True)
        df_commanders.drop_duplicates(inplace=True)

        df = pd.DataFrame()
        for (fullname, num_decks, urlname) in df_commanders.values:
            dfnow = commander_summary(urlname)

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
    js = [
        _.text for _ in root.xpath('.//div[@class="container"]/script')
        if _.text and 'json_dict' in _.text
    ][0]

    startstr = 'const json_dict = '
    assert js.startswith(startstr)
    js = js[len(startstr):-1]

    j = json.loads(js)['cardlists']

    if j is None:
        # no info, empty df is okay
        return pd.DataFrame()

    if include_multicards:
        dfsummary = pd.DataFrame([
            {
                'cardlist_tag': cardlist['tag'],
                'url': cardview['url'],
                'label': cardview['label'],
                'name': cardview['name'],
                'price': cardview.get('cardkingdom', {}).get('price'),
                'cardkingdom_url': cardview.get('cardkingdom', {}).get('url'),
                'variation': cardview.get('cardkingdom', {}).get('variation'),
                'is_commander': card.get('is_commander'),
                'is_banned': card.get('is_banned'),
                'is_unofficial': card.get('is_unofficial'),
                'image': card.get('image'),
            }
            for cardlist in j
            for cardview in cardlist['cardviews']
            for card in cardview.get('cards', [])
        ])
    else:
        dfsummary = pd.DataFrame([
            {
                'cardlist_tag': cardlist['tag'],
                'url': cardview['url'],
                'label': cardview['label'],
                'name': cardview['name'],
                'price': (cardview.get('cardkingdom', {}) or {}).get('price'),
                'url': (cardview.get('cardkingdom', {}) or {}).get('url'),
                'variation': (cardview.get('cardkingdom', {}) or {}).get('variation'),
                'is_commander': cardview.get('cards', [{}])[0].get('is_commander'),
                'is_banned': cardview.get('cards', [{}])[0].get('is_banned'),
                'is_unofficial': cardview.get('cards', [{}])[0].get('is_unofficial'),
                'image': cardview.get('cards', [{}])[0].get('image'),
            }
            for cardlist in j
            for cardview in cardlist['cardviews']
        ])

    return dfsummary


def main():
    """docstring

    args:

    returns:

    raises:

    """
    pass


# ----------------------------- #
#   Command line                #
# ----------------------------- #

def parse_args():
    """ Take a log file from the commmand line """
    parser = argparse.ArgumentParser()
    parser.add_argument("-x", "--xample", help="An Example", action='store_true')

    args = parser.parse_args()

    logger.debug("arguments set to {}".format(vars(args)))

    return args


if __name__ == '__main__':
    args = parse_args()
    main()

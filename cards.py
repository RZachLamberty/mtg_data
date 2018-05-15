#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: cards.py
Author: zlamberty
Created: 2016-02-28

Description:
    cards class

Usage:
    <usage>

"""

import logging
import os
import requests

import pandas as pd

import common

from mtgconstants import BASIC_LANDS


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

# data sources
CARD_URL = 'http://mtgjson.com/json/AllSets.json'

# local html caching
HTML_DIR = os.path.join(os.sep, 'tmp', 'local_html_cache')

# ----------------------------- #
#   card class                  #
# ----------------------------- #

class JsonCardParseError(Exception):
    pass


class MtgCard(dict):
    """Simple card object; as most of the cards are already coming to as us
    JSON objects, this will be pretty trivial

    """
    pass


def get_cards(url=CARD_URL):
    """Download all card data from mtgjson.com (see
    http://mtgjson.com/documentation.html for more information about the various
    fields available to us)

    args:
        url: base url of mtgjson api (default: scrape.CARD_URL)

    returns:
        iterable of MtgCard objects

    raises:
        None

    """
    # download the JSON file
    cards = requests.get(url).json()

    # iterate through the json objects, parsing one at a time into card objects
    for setname, setdict in cards.items():
        for card in setdict['cards']:
            c = MtgCard()
            c.update(card)
            c.update({'setname': setname})
            yield c


def all_land_card_names(url=CARD_URL):
    return {
        _.get('name') for _ in get_cards(url) if 'Land' in _.get('types', [])
    }


def all_card_names(url=CARD_URL, ignore_lands=True):
    """a set of all the card names. ignore basic lands by default"""
    cns = {_.get('name') for _ in get_cards(url)}
    if ignore_lands:
        cns = cns.difference(all_land_card_names(url))
    return cns


def cards_df(url=CARD_URL):
    """Same as get_cards, but returns a pandas dataframe

    args:
        url: base url of mtgjson api (default: scrape.CARD_URL)

    returns:
        pandas dataframe of mtg cards

    """
    return pd.DataFrame(get_cards(url))

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


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

# data sources
CARD_URL = 'http://mtgjson.com/json/AllSets.json'

# local html caching
HTML_DIR = os.path.join(os.sep, 'tmp', 'local_html_cache')

logger = logging.getLogger(__name__)


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
            yield c


def cards_df(url=CARD_URL):
    """Same as get_cards, but returns a pandas dataframe

    args:
        url: base url of mtgjson api (default: scrape.CARD_URL)

    returns:
        pandas dataframe of mtg cards

    """
    return pd.DataFrame(get_cards(url))

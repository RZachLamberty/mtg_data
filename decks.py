#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: decks.py
Author: zlamberty
Created: 2016-02-28

Description:
    MTG card deck class

Usage:
    <usage>

"""

import logging


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

DECK_URL = 'http://sales.starcitygames.com//deckdatabase/deckshow.php?'

logger = logging.getLogger(__name__)


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

class MtgDeck(object):
    """Abstract base class for other decks to inherit (defines the interface)"""
    def __init__(self):
        raise NotImplementedError


def _get_decks(deckurls, decktype):
    """download all decks of a certain deck type from a base url

    args:
        deckurls: (iterable of strings) the urls of our decks
        decktype: (class) the class of the decks we will build (must inherit
            from MtgDeck)

    returns:
        generator of deck objects

    raises:
        None

    """
    for deckurl in deckurls:
        yield decktype(url=deckurl)

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

import common

from py2neo import neo4j, Graph


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

# data sources
CARD_URL = 'http://mtgjson.com/json/AllSets.json'

# local html caching
HTML_DIR = os.path.join(os.sep, 'tmp', 'local_html_cache')

# neo4j db
INSERT_QRY = """
MERGE (s:MtgSet {code: {mtgset}.code})
  ON CREATE SET
    s.name = {mtgset}.name,
    s.releaseDate = {mtgset}.releaseDate,
    s.type = {mtgset}.type
WITH {mtgset}.cards as mtgcards, s
UNWIND mtgcards  as mtgcard
MERGE (card:MtgCard {id: LOWER(mtgcard.name)})
  ON CREATE SET
    card.artist = mtgcard.artist,
    card.cmc = mtgcard.cmc,
    card.colorIdentity = mtgcard.colorIdentity,
    card.colors = mtgcard.colors,
    card.imageName = mtgcard.imageName,
    card.layout = mtgcard.layout,
    card.manaCost = mtgcard.manaCost,
    card.mciNumber = mtgcard.mciNumber,
    card.multiverseid = mtgcard.multiverseid,
    card.name = mtgcard.name,
    card.number = mtgcard.number,
    card.power = mtgcard.power,
    card.rarity = mtgcard.rarity,
    card.subtypes = mtgcard.subtypes,
    card.text = mtgcard.text,
    card.toughness = mtgcard.toughness,
    card.type = mtgcard.type,
    card.types = mtgcard.types,
    card.mtg_id = mtgcard.id
MERGE (card)-[:PART_OF_SET]->(s)
"""

logging.getLogger('py2neo').setLevel(logging.WARNING)
logging.getLogger('httpstream').setLevel(logging.WARNING)
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
            c.update({'setname': setname})
            yield c


def cards_df(url=CARD_URL):
    """Same as get_cards, but returns a pandas dataframe

    args:
        url: base url of mtgjson api (default: scrape.CARD_URL)

    returns:
        pandas dataframe of mtg cards

    """
    return pd.DataFrame(get_cards(url))


def json_to_neo4j(url=CARD_URL, neo4jurl=common.NEO4J_URL):
    """neo4j can directly load json, we just have to get the query right. I
    think I have!

    args:
        url: (str) the url of the cards (must be a json api endpoint)
        user: (str) username for the neo4j db
        pw: (str) password for the neo4j db

    returns:
        None

    """
    # card name and set uniqueness
    graph = Graph(neo4jurl)

    graph.cypher.execute("create constraint on (s:MtgSet) assert s.code is unique")
    graph.cypher.execute("create constraint on (c:MtgCard) assert c.id is unique")

    logger.info('getting card data from {}'.format(url))
    jcards = requests.get(url).json()
    logger.info('bulk loading to neo4j')
    for (setid, setdict) in jcards.items():
        logger.debug("inserting set {}".format(setid))
        graph.cypher.execute(INSERT_QRY, {'mtgset': setdict})

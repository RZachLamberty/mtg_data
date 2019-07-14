#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: graphdb.py
Author: zlamberty
Created: 2018-05-14

Description:
    utilities for persisting information to graph databases (for now, neo4j
    only)

Usage:
    <usage>

"""

import itertools
import logging
import os

import requests

from neo4j import GraphDatabase, basic_auth

from mtg import utils
from mtg.cards import CARD_URL
from mtg.extract.scg import ScgDeckParseError, scg_decks

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')

LOGGER = logging.getLogger(__name__)
logging.getLogger('py2neo').setLevel(logging.WARNING)
logging.getLogger('httpstream').setLevel(logging.WARNING)

# ----------------------------- #
#   mtgjson uploading           #
# ----------------------------- #

MTGJSON_INSERT_QRY = """
MERGE (s:MtgSet {code: {mtgset}.code})
  ON CREATE SET
    s.name = {mtgset}.name,
    s.releaseDate = {mtgset}.releaseDate,
    s.type = {mtgset}.type
WITH {mtgset}.cards AS mtgcards, s
UNWIND mtgcards AS mtgcard
MERGE (card:MtgCard {id: lower(mtgcard.name)})
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


def mtgjson_to_neo4j(url=CARD_URL, neo4juri=utils.NEO4J_URI, username=None,
                     password=None):
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
    driver = GraphDatabase.driver(neo4juri, auth=basic_auth(username, password))
    with driver.session() as session:
        session.run("CREATE CONSTRAINT ON (s:MtgSet) ASSERT s.code IS UNIQUE")
        session.run("CREATE CONSTRAINT ON (c:MtgCard) ASSERT c.id IS UNIQUE")

        LOGGER.info('getting card data from {}'.format(url))
        jcards = requests.get(url).json()
        LOGGER.info('bulk loading to neo4j')
        for (setid, setdict) in jcards.items():
            LOGGER.debug("inserting set {}".format(setid))
            session.run(MTGJSON_INSERT_QRY, {'mtgset': setdict})


# ----------------------------- #
#   scg2 deck uploading          #
# ----------------------------- #

SCG_INSERT_DECKS_QRY = """
UNWIND {decks} AS deck
MERGE (d:MtgDeck {id: deck.url})
  ON CREATE SET
    d :SCG,
    d.author = deck.author,
    d.authorurl = deck.authorurl,
    d.date = deck.date,
    d.event = deck.event,
    d.eventurl = deck.eventurl,
    d.finish = deck.finish,
    d.name = deck.name,
    d.url = deck.url,
    d.format = deck.format
"""

SCG_INSERT_BOARDS_QRY = """
UNWIND {decks} AS deck
MATCH (d:MtgDeck {id: deck.url})
WITH deck.mainboard AS mainboard, deck.sideboard AS sideboard, d
UNWIND mainboard AS card
MATCH (c:MtgCard {id: card.cardname})
WITH card, d, c, sideboard
MERGE (d)<-[r:MAINBOARD]-(c)
  ON CREATE SET
    r.qty = card.qty
WITH sideboard, d
UNWIND sideboard AS card
MATCH (c:MtgCard {id: card.cardname})
WITH card, d, c
MERGE (d)<-[r:SIDEBOARD]-(c)
  ON CREATE SET
    r.qty = card.qty
"""


def _chunks(n, iterable):
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, n))
        if not chunk:
            return
        yield chunk


def load_scg_decks_to_neo4j(neo4juri=NEO4J_URI, username=None, password=None):
    driver = GraphDatabase.driver(neo4juri, auth=basic_auth(username, password))

    with driver.session() as session:
        # card name and set uniqueness
        session.run("CREATE CONSTRAINT ON (d:MtgDeck) ASSERT d.id IS UNIQUE")

    LOGGER.info('bulk loading to neo4j')
    for deckchunk in _chunks(1000, scg_decks()):
        jsonchunk = []
        for d in deckchunk:
            try:
                jsonchunk.append(d.to_dict())
            except ScgDeckParseError:
                continue

        with driver.session() as session:
            session.run(SCG_INSERT_DECKS_QRY, parameters={'decks': jsonchunk})
            session.run(SCG_INSERT_BOARDS_QRY, parameters={'decks': jsonchunk})

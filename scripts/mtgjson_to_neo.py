#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: mtgjson_to_neo
Created: 2019-07-14

Description:

    script for pushing mtgjson card data (loaded via the mtg.cards module) to
    neo4j

Usage:

    $> python mtgjson_to_neo.py

"""

import logging

import requests

from neo4j import GraphDatabase, basic_auth

from mtg.cards import CARD_URL
from mtg.credentials import F_NEO_CONF, load_neo_config
from mtg.load.nx2neo import verify_constraints
from mtg.utils import init_logging

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

LOGGER = logging.getLogger(__name__)

logging.getLogger('py2neo').setLevel(logging.WARNING)
logging.getLogger('httpstream').setLevel(logging.WARNING)


# ----------------------------- #
#   mtgjson uploading           #
# ----------------------------- #

MTGJSON_INSERT_QRY = """
MERGE (s:Set {code: {mtgset}.code})
  ON CREATE SET
    s.name = {mtgset}.name,
    s.releaseDate = {mtgset}.releaseDate,
    s.type = {mtgset}.type
WITH {mtgset}.cards AS mtgcards, s
UNWIND mtgcards AS mtgcard
MERGE (card:Card {id: lower(mtgcard.name)})
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


def main(url=CARD_URL, f_neo_conf=F_NEO_CONF):
    """neo4j can directly load json, we just have to get the query right. I
    think I have!

    args:
        url (str): the url of the cards (must be a json api endpoint)
        f_neo_conf (str): path to yaml file with config for neo4j connection

    returns:
        None

    """
    neo_conf = load_neo_config(f_neo_conf)

    # card name and set uniqueness
    constraints = [('Card', 'name'),
                   ('Set', 'name')]
    neo4juri = 'bolt://{ip}:{port}'.format(**neo_conf)
    auth = basic_auth(neo_conf['user'], neo_conf['pw'])
    with GraphDatabase.driver(neo4juri, auth=auth) as driver:
        with driver.session() as session:
            verify_constraints(session, constraints)

            LOGGER.info('getting card data from {}'.format(url))
            jcards = requests.get(url).json()

            LOGGER.info('bulk loading to neo4j')
            for (setid, setdict) in jcards.items():
                LOGGER.debug("inserting set {}".format(setid))
                session.run(MTGJSON_INSERT_QRY, {'mtgset': setdict})


if __name__ == "__main__":
    init_logging()
    main()

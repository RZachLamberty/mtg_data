#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: neo4j
Created: 2019-07-20

Description:

    loading material from neo4j into established item types in the mtg directory

Usage:

    >>> import neo4j

"""

import logging

from neo4j import basic_auth as _basic_auth, GraphDatabase as _GraphDatabase

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

LOGGER = logging.getLogger('bulk_rename_tappedout_tags')
LOGGER.setLevel(logging.DEBUG)

# ----------------------------- #
#   tags                        #
# ----------------------------- #

KNOWN_NODES_QRY = "MATCH (n:Tag) RETURN DISTINCT n.name AS name"
KNOWN_ALIAS_TAGS_QRY = "MATCH (n:TappedOutTag) RETURN DISTINCT n.name AS name"
KNOWN_ALIAS_RELS_QRY = """MATCH (n1:TappedOutTag)-[:IS_ALIAS_OF]->(n2:Tag)
RETURN n1.name AS tappedout_tag,
       n2.name AS tag"""


def get_neo_tags(neo_conf):
    neo4juri = 'bolt://{ip}:{port}'.format(**neo_conf)
    auth = _basic_auth(neo_conf['user'], neo_conf['pw'])
    with _GraphDatabase.driver(neo4juri, auth=auth) as driver:
        with driver.session() as session:
            LOGGER.info('loading all known tags from {}'.format(neo4juri))
            resp = session.run(KNOWN_NODES_QRY)
            known_tags = {_['name'] for _ in resp.data()}

            LOGGER.info(
                'loading all known tapped out alias tags from {}'.format(
                    neo4juri))
            resp = session.run(KNOWN_ALIAS_TAGS_QRY)
            alias_tags = {_['name'] for _ in resp.data()}

            LOGGER.info(
                'loading all known tapped out alias connections from {}'.format(
                    neo4juri))
            resp = session.run(KNOWN_ALIAS_RELS_QRY)
            aliases = [[_['tappedout_tag'], _['tag']] for _ in resp.data()]

            return known_tags, alias_tags, aliases


ALL_OFFICIAL_TAGS_QRY = """UNWIND $card_names AS card_name
MATCH (c:Card {name: card_name})-[*]->(t:Tag)
RETURN DISTINCT c.name, t.name"""


def get_card_official_tags(neo_conf, card_names):
    neo4juri = 'bolt://{ip}:{port}'.format(**neo_conf)
    auth = _basic_auth(neo_conf['user'], neo_conf['pw'])
    with _GraphDatabase.driver(neo4juri, auth=auth) as driver:
        with driver.session() as session:
            LOGGER.info(
                'loading all official tags for {} cards'.format(
                    len(card_names)))
            resp = session.run(ALL_OFFICIAL_TAGS_QRY, card_names=card_names)
            return [[_['c.name'], _['t.name']] for _ in resp.data()]

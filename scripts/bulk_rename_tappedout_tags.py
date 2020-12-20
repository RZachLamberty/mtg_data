#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: bulk_rename_tappedout_tags
Created: 2019-07-15

Description:

    iterate through the tags that exist currently on tappedout, and for each
    of those tags, if they are not currently in our neo database, do one of
    the two following things:

        1. accept that as a valid new tag
        2. remap it to an existing tag

    there will be an interactive process to do this; for now it will be a cli
    tool but this might make more sense as a notebook long-term

Usage:

    $> python bulk_rename_tappedout_tags.py

"""

import logging

from neo4j import basic_auth, GraphDatabase

from mtg.credentials import F_NEO_CONF, load_neo_config
from mtg.extract.tappedout import get_all_categories
from mtg.load.neo import digraph_to_neo, verify_constraints, NeoConstraint
from mtg.utils import init_logging

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

LOGGER = logging.getLogger('bulk_rename_tappedout_tags')
LOGGER.setLevel(logging.DEBUG)

KNOWN_NODES_QRY = "MATCH (n:Tag) RETURN DISTINCT n.name AS name"


# ----------------------------- #
#   main function               #
# ----------------------------- #

def get_neo_tags(neo_conf):
    neo4juri = 'bolt://{ip}:{port}'.format(**neo_conf)
    auth = basic_auth(neo_conf['user'], neo_conf['pw'])
    with GraphDatabase.driver(neo4juri, auth=auth) as driver:
        with driver.session() as session:
            LOGGER.info('loading all known tags from {}'.format(neo4juri))
            resp = session.run(KNOWN_NODES_QRY)
            return {_['name'] for _ in resp.data()}


def build_tag_remapping(tappedout_tags, known_tags):
    tappedout_tag_values = {tag.replace('#', '').replace('_', ' ')
                            for deck_id, tag_dict in tappedout_tags.items()
                            for card_name, tag_list in tag_dict.items()
                            for tag in tag_list}
    unknown_tags = sorted(set(tappedout_tag_values).difference(known_tags))

    # todo: finish this


def build_tag_graphs(tappedout_tags, tag_remapping):
    # todo: finish this
    pass


def main(f_neo_conf=F_NEO_CONF, tapped_out_owner='ndlambo'):
    # todo: add entrypoint here
    neo_conf = load_neo_config(f_neo_conf)

    known_tags = get_neo_tags(neo_conf)
    tappedout_tags = get_all_categories(tapped_out_owner)

    tag_remapping = build_tag_remapping(tappedout_tags, known_tags)
    nx_new_tags, nx_card_tags = build_tag_graphs(tappedout_tags, tag_remapping)

    # push graphs to neo4j
    constraints = [NeoConstraint('Tag', 'name')]
    digraph_to_neo(nx_new_tags, neo_conf, constraints)
    digraph_to_neo(nx_card_tags, neo_conf, constraints)


if __name__ == "__main__":
    init_logging()
    main()

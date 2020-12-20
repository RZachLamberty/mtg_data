#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: metamox_to_neo
Created: 2019-07-14

Description:

    script for loading metamox tags and persisting them to neo4j

Usage:

    $> python metamox_to_neo.py

"""

import networkx as nx

from mtg.credentials import F_NEO_CONF, load_neo_config
from mtg.extract import metamox
from mtg.load.neo import digraph_to_neo, NeoConstraint
from mtg.utils import init_logging


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

# ----------------------------- #
#   helper functions            #
# ----------------------------- #

def build_tag_graphs(metamox_tags):
    df_tags = (metamox_tags
               [['tag', 'subtag']]
               .sort_values(by=['tag', 'subtag'])
               .drop_duplicates())

    nx_tags = nx.DiGraph()
    nx_tags.add_nodes_from(df_tags.tag.unique(), label='Tag')
    nx_tags.add_nodes_from(df_tags.subtag.unique(), label='Tag')
    nx_tags.add_edges_from((df_tags
                            [['subtag', 'tag']]
                            [df_tags.subtag.notna()]
                            .values),
                           _type='IS_SUBTAG_OF')

    metamox_tags.loc[:, 'dst'] = (metamox_tags
                                  .subtag
                                  .where(metamox_tags.subtag.notnull(),
                                         metamox_tags.tag))

    nx_card_tags = nx.DiGraph()
    nx_card_tags.add_nodes_from(metamox_tags.name.unique(), label='Card')
    nx_card_tags.add_nodes_from(metamox_tags.dst.unique(), label='Tag')
    nx_card_tags.add_edges_from(metamox_tags[['name', 'dst']].values,
                                _type='HAS_TAG')

    return nx_tags, nx_card_tags


# ----------------------------- #
#   main function               #
# ----------------------------- #

# todo: add entrypoint here
def main(f_neo_conf=F_NEO_CONF):
    neo_conf = load_neo_config(f_neo_conf)

    # get tags
    metamox_tags = metamox.get_all_tags().drop(columns='index')
    nx_tags, nx_card_tags = build_tag_graphs(metamox_tags)

    # push graphs to neo4j
    constraints = [NeoConstraint('Tag', 'name')]
    digraph_to_neo(nx_tags, neo_conf, constraints)
    digraph_to_neo(nx_card_tags, neo_conf, constraints)


if __name__ == "__main__":
    init_logging()
    main()

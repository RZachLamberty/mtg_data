#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: nx2neo.py
Author: zlamberty
Created: 2018-06-23

Description:
    persist networkx graphs to neo4j

Usage:

    >>> import nx2neo
    >>> # verify that the uniqueness constraints exist
    >>> nx2neo.verify_constraints()

"""

import json
import logging

from neo4j import GraphDatabase, basic_auth

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

LOGGER = logging.getLogger(__name__)
logging.getLogger('neo4j').setLevel(logging.WARNING)
LOGGER.setLevel(logging.INFO)

MTG_CONSTRAINTS = [('Tag', 'name'),
                   ('Deck', 'name'),
                   ('Card', 'name'),
                   ('TappedoutCategory', 'name'), ]


# ----------------------------- #
#   main functions              #
# ----------------------------- #

class MtgNeo4jError(Exception):
    pass


def verify_constraints(session, constraints=None):
    if constraints is None:
        constraints = MTG_CONSTRAINTS

    for (label, prop) in constraints:
        session.run(
            'CREATE CONSTRAINT ON (n:{}) ASSERT n.{} IS UNIQUE'.format(label,
                                                                       prop))


def make_node_qry(node_name, properties):
    node_label = properties.get('label')
    if node_label is None:
        raise MtgNeo4jError("all nodes must have labels to be added to neo4j")

    merge_str = 'MERGE (n:{label} {{name: "{name}"}})'.format(label=node_label,
                                                              name=node_name, )

    set_str = []
    for (attr, val) in properties.items():
        if attr != 'label':
            set_str.append('n.{} = {}'.format(attr, json.dumps(val)))
    set_str = ', '.join(set_str)

    on_create_str = 'ON CREATE SET {}'.format(set_str) if set_str else ''

    return_str = "return id(n)"

    qry = ' '.join([merge_str, on_create_str, return_str])

    return qry


def make_edge_qry(src, src_label, dst, dst_label, properties):
    edge_type = properties.get('_type')
    if edge_type is None:
        raise MtgNeo4jError(
            "all edges must have a type (key is \"_type\") to be added to "
            "neo4j")

    nodefmt = '({alias}:{label} {{name: "{name}"}})'
    src_node_str = nodefmt.format(alias='src', label=src_label, name=src)
    dst_node_str = nodefmt.format(alias='dst', label=dst_label, name=dst)

    merge_str = "MATCH {src:} MATCH {dst:} MERGE (src)-[e:{etype}]->(dst)"
    merge_str = merge_str.format(src=src_node_str,
                                 etype=edge_type,
                                 dst=dst_node_str, )

    set_str = []
    for (attr, val) in properties.items():
        if attr != '_type':
            set_str.append('e.{} = {}'.format(attr, json.dumps(val)))
    set_str = ', '.join(set_str)

    on_create_str = 'on create set {}'.format(set_str) if set_str else ''

    return_str = "return id(e)"

    qry = ' '.join([merge_str, on_create_str, return_str])

    return qry


# todo: figure out whether this will work with a regular graph (not just a
#  digraph, that is)
def digraph_to_neo(digraph, dbconf, constraints=None):
    """persist a digraph to a neo4j database

    args:
        digraph (nx.DiGraph): any directed graph where the nodes have (at
            least) a `label` property. for example, the category graph as
            created in `tappedout.py`
        dbconf (dict): dictionary of connection information for the neo4j
            datbase. must contain the keys "ip", "port", "user", and "pw"
        constraints (iterable): a list of pairs of items defining the neo4j
            constraint. the first value in each pair is the Label (e.g.
            :Person); the second is any one property we are demanding to be
            unique. see `verify_constraints` for more details.

    """
    url = 'bolt://{}:{}'.format(dbconf["ip"], dbconf["port"])
    auth = basic_auth(dbconf["user"], dbconf["pw"])
    with GraphDatabase.driver(url, auth=auth) as driver:
        with driver.session() as session:
            verify_constraints(session, constraints)

            # handle nodes first, then handle edges
            LOGGER.info('updating nodes in neo4j')
            for i, (node_name, properties) in enumerate(
                    digraph.nodes(data=True)):
                qry = make_node_qry(node_name, properties)
                LOGGER.debug(qry)
                res = session.run(qry)

            LOGGER.info('updating relationships in neo4j')
            for i, (src, dst, properties) in enumerate(
                    digraph.edges(data=True)):
                src_label = digraph.node[src]['label']
                dst_label = digraph.node[dst]['label']
                qry = make_edge_qry(src, src_label, dst, dst_label, properties)
                LOGGER.debug(qry)
                res = session.run(qry)

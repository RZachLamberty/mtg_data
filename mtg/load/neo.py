#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: neo.py
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

from dataclasses import dataclass

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


@dataclass
class NeoNode:
    name: str
    label: str
    attributes: dict = None

    def neo_repr(self, alias='n'):
        return f'({alias}:{self.label} {{name: "{self.name}"}})'

    @property
    def query(self):
        merge_str = f'MERGE {self.neo_repr()}'

        attrs = self.attributes or {}
        set_str = ', '.join([f'n.{key} = {json.dumps(value)}'
                             for (key, value) in attrs.items()])

        on_create_str = 'ON CREATE SET {}'.format(set_str) if set_str else ''

        return_str = "RETURN id(n)"

        qry = ' '.join([merge_str, on_create_str, return_str])

        return qry


@dataclass
class NeoRelationship:
    src: NeoNode
    dst: NeoNode
    _type: str
    properties: dict = None
    directed: bool = True

    def edge_repr(self, alias='e'):
        return f'[{alias}:{self._type}]'

    @property
    def arrow(self):
        return '>' if self.directed else ''

    @property
    def query(self):
        merge_str = (f"MATCH {self.src.neo_repr(alias='src')} "
                     f"MATCH {self.dst.neo_repr(alias='dst')} "
                     f"MERGE (src)-{self.edge_repr()}-{self.arrow}(dst)")

        props = self.properties or {}
        set_str = ', '.join([f'n.{key} = {json.dumps(value)}'
                             for (key, value) in props.items()])

        on_create_str = f'ON CREATE SET {set_str}' if set_str else ''

        return_str = "RETURN id(e)"

        qry = ' '.join([merge_str, on_create_str, return_str])

        return qry


@dataclass
class NeoConstraint:
    label: str
    attribute: str

    @property
    def query(self):
        return (f'CREATE CONSTRAINT ON (n:{self.label})'
                f'ASSERT n.{self.attribute} IS UNIQUE')


def verify_constraints(session, constraints=None):
    if constraints is None:
        constraints = MTG_CONSTRAINTS

    for constraint in constraints:
        session.run(constraint.query)


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
        constraints (iterable): a list of `NeoConstraint` objects

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
                label = properties['label']
                attributes = {k: v
                              for (k, v) in properties.items() if k != 'label'}
                n = NeoNode(name=node_name,
                            label=label,
                            attributes=attributes)
                LOGGER.debug(n.query)
                _ = session.run(n.query)

            LOGGER.info('updating relationships in neo4j')
            for i, (src, dst, properties) in enumerate(
                    digraph.edges(data=True)):
                src_node = NeoNode(name=src,
                                   label=digraph.node[src]['label'])
                dst_node = NeoNode(name=dst,
                                   label=digraph.node[dst]['label'])

                _type = properties['_type']
                clean_properties = {k: v
                                    for (k, v) in properties.items()
                                    if k != '_type'}

                r = NeoRelationship(src=src_node,
                                    dst=dst_node,
                                    _type=_type,
                                    properties=clean_properties)

                LOGGER.debug(r.query)
                _ = session.run(r.query)
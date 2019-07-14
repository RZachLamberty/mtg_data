#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: tags.py
Author: zlamberty
Created: 2018-06-09

Description:

    this module is an implementation of a Tag object interface for use in mtg
    deck building

    "tags" in the context of mtg cards are a categorization with a hierarchy.
    the general idea is to be able to talk about over-arching themes,
    utilities, special use cases, as a collection of cards that have certain
    abilities, or to look at a single card as having a collection of those
    categorizations.

    it's important to note that tags themselves can be hierarchical: e.g. while
    removal is an important tag in its own right, there are several types of
    removal and a given card could have multiple. for example:

        + removal > artifact
        + removal > enchantment
        + removal > graveyard
        + removal > land
        + removal > all

    in building a commander deck it is important to know that you have e.g.
    at least *some* targeted enchantment removal, so while having lots of
    removal is good having full coverage is the real goal

Usage:
<usage>

"""

import copy
import logging
import os

import networkx as nx
import yaml

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

HERE = os.path.dirname(os.path.realpath(__file__))
LOGGER = logging.getLogger('tags')
F_TAGS = os.path.join(HERE, 'tags.yaml')


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

class MtgTagError(Exception):
    pass


class Tags(object):
    def __init__(self):
        self.tags = nx.DiGraph()
        self._fyaml = None
        self._tagdict = None

    def init_from_yaml(self, fyaml=F_TAGS):
        self._fyaml = fyaml
        with open(self._fyaml, 'r') as fp:
            self._tagdict = yaml.load(fp, Loader=yaml.FullLoader)
        self._tagdict.pop('_yaml_variables')
        self._tagdict_to_nodes()

    def _tagdict_to_nodes(self, parent_node=None, tagdict=None):
        if parent_node is None:
            parent_node = 'mtg'
            self.tags.add_node(parent_node)

        tagdict = tagdict or self._tagdict

        for (tag, val) in tagdict.items():
            tag_node = '{}:{}'.format(parent_node, tag)
            # create an edge from parent to tag (adds tag as a convenient
            # side-effect)
            self.tags.add_edge(tag_node, parent_node)
            if val is None:
                # tag is a leaf node, we're done with this one
                continue
            elif isinstance(val, dict):
                self._tagdict_to_nodes(parent_node=tag_node,
                                       tagdict=copy.deepcopy(val))
            else:
                raise MtgTagError("unhandled tag structure")

    def child_parent_iter(self):
        return ((e[0], e[1])
                for e in nx.edge_dfs(self.tags, 'mtg', orientation='reverse'))

    def plot_graph(self):
        try:
            import matplotlib.pyplot as plt
            from networkx.drawing.nx_agraph import graphviz_layout
        except (ImportError, ModuleNotFoundError):
            LOGGER.error(
                "matplotlib and graphvix must be installed to execute this "
                "function")
            raise

        pos = graphviz_layout(self.tags, prog='twopi', args='')
        plt.figure(figsize=(16, 16))
        nx.draw(self.tags, pos, node_size=20, alpha=0.5, node_color='blue',
                with_labels=True)
        plt.show()

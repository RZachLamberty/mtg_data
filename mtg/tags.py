#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: tags.py
Author: zlamberty
Created: 2018-06-09

Description:


Usage:
<usage>

"""

import copy
import logging
import os

import anytree
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


class MtgNode(anytree.Node):
    @property
    def longname(self):
        return self.separator.join(
            [""] + [_.name for _ in self.path if _.name != 'mtg'])

    @property
    def tappedout_name(self):
        return '#{}'.format('_'.join(_.name.replace(' ', '_').replace('/', '')
                                     for _ in self.path
                                     if _.name != 'mtg'))


class TagsOld(object):
    def __init__(self, fyaml=F_TAGS):
        with open(fyaml, 'r') as f:
            self._tagdict = yaml.load(f)
        self._tagdict.pop('_yaml_variables')
        self._tagdict_to_nodes()

    def _tagdict_to_nodes(self, parent_node=None, tagdict=None):
        if parent_node is None:
            parent_node = self.tags = MtgNode(name='mtg')

        if tagdict is None:
            tagdict = self._tagdict

        for (tag, val) in tagdict.items():
            this_node = MtgNode(name=tag, parent=parent_node)
            if val is None:
                # tag is a leaf node, we're done with this one
                continue
            elif isinstance(val, dict):
                self._tagdict_to_nodes(parent_node=this_node,
                                       tagdict=copy.deepcopy(val))
            else:
                raise MtgTagError("unhandled tag structure")

    def __str__(self):
        return '\n'.join(['{}{}'.format(pre, node.name)
                          for pre, fill, node in anytree.RenderTree(self.tags)])

    def __iter__(self):
        return anytree.PreOrderIter(self.tags)


class Tags(object):
    def __init__(self, fyaml=F_TAGS):
        with open(fyaml, 'r') as f:
            self._tagdict = yaml.load(f)
        self._tagdict.pop('_yaml_variables')
        self.tags = nx.DiGraph()
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
        except ImportError:
            raise

        pos = graphviz_layout(self.tags, prog='twopi', args='')
        plt.figure(figsize=(16, 16))
        nx.draw(self.tags, pos, node_size=20, alpha=0.5, node_color='blue',
                with_labels=True)
        plt.show()
t
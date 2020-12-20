#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: tags
Author: zlamberty
Created: 2018-06-09

Description:

    this module is an implementation of a Tag object interface for use in mtg
    deck building. the ultimate data structure is whatever I implement in a
    neo4j graph database of tags, where I will have an ultimate "official" tag
    and then a sub-strata of tags that are associated with various sites and
    cards that have those tags.

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

    >>> import mtg.tags

"""

import logging as _logging
from collections import defaultdict

from IPython.display import display
from ipywidgets import Button, Checkbox, Dropdown, Output, Text
from neo4j import basic_auth as _basic_auth, GraphDatabase as _GraphDatabase

from mtg.extract.neo4j import get_neo_tags
from mtg.load.neo import (NeoConstraint as _NeoConstraint,
                          verify_constraints as _verify_constraints, NeoNode,
                          NeoRelationship)

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

_LOGGER = _logging.getLogger(__name__)
_LOGGER.setLevel(_logging.DEBUG)

OFFICIAL_TAG_LABEL = 'Tag'


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

class MtgTagError(Exception):
    pass


def tag_is_alias(tag, session):
    q = (f"MATCH p={tag.neo_repr()}-[:IS_ALIAS_OF]->(o:{OFFICIAL_TAG_LABEL}) "
         f"RETURN count(p) as num_aliases")
    resp = session.run(q)
    return resp.data()[0]['num_aliases'] > 0


class Tags(object):
    """this is an interface class defining the minimum functionality that
    must be implemented in children classes that interface directly with
    different sources

    """

    def __init__(self, db_conf, tag_label=OFFICIAL_TAG_LABEL,
                 id_attribute='name'):
        self.db_conf = db_conf
        self.tag_label = tag_label
        self.id_attribute = id_attribute

        # db stuff
        self.init_db()
        self.get_known_tags()

    # TO BE IMPLEMENTED IN CHILD CLASS -----------------------------------------
    @property
    def cards(self):
        raise NotImplementedError()

    @property
    def tags(self):
        raise NotImplementedError()

    @property
    def constraints(self):
        raise NotImplementedError()

    @property
    def card_tags(self):
        raise NotImplementedError()

    @property
    def tag_hierarchy(self):
        raise NotImplementedError()

    @property
    def tag_normalization(self):
        raise NotImplementedError()

    @tag_normalization.getter
    def tag_normalization(self):
        return self._tag_normalization

    @tag_normalization.setter
    def tag_normalization(self, tag_normalization):
        self._tag_normalization = tag_normalization

    # neo4j stuff --------------------------------------------------------------
    def init_db(self):
        """various database initializations"""
        constraints = [_NeoConstraint(label=self.tag_label,
                                      attribute=self.id_attribute)]
        with _GraphDatabase.driver(self.url, auth=self.auth) as driver:
            with driver.session() as session:
                _verify_constraints(session, constraints)

    @property
    def url(self):
        return 'bolt://{ip:}:{port:}'.format(**self.db_conf)

    @property
    def auth(self):
        return _basic_auth(self.db_conf["user"], self.db_conf["pw"])

    def get_known_tags(self):
        known_tags, alias_tags, aliases = get_neo_tags(self.db_conf)
        self.official_tags = [NeoNode(name=name, label=OFFICIAL_TAG_LABEL)
                              for name in known_tags]
        self.alias_tags = alias_tags
        self.aliases = aliases

    # publication helper function ----------------------------------------------
    def publish_to_neo(self):
        """publish internal node lists and mappings if they exist

        this will happen in stages:

            1. add all internal constraints
            1. add all internal nodes
            1. add all internal relationships

        constraints will pulled from `self.constraints`.

        for nodes, we will publish the following attributes

            + `self.cards` (iter of NeoNode instances with label='Card')
            + `self.tags` (iter of NeoNode instances with custom labels)

        we support the following iterables of NeoRelationship instances:

            + `self.card_tags`
                + (c:Card)-[:HAS_TAG]->(t:ThisTagType)
            + `self.tag_hierarchy`
                + (t:ThisTagType)-[:IS_SUBTAG_OF]->(t:ThisTagType)
            + `self.tag_normalization`
                + (t:ThisTagType)-[:Is_ALIAS_OF]->(ot:Tag)

        """
        queries = []

        self_attributes = ['constraints', 'cards', 'tags', 'card_tags',
                           'tag_hierarchy', 'tag_normalization']

        for attr in self_attributes:
            _LOGGER.info('looking for queries for {}'.format(attr))
            try:
                queries += [elem.query for elem in getattr(self, attr)]
            except AttributeError:
                msg = (f"you haven't constructed attribute '{attr}' and "
                       f"therefore nothing will be published")
                _LOGGER.warning(msg)
            except Exception as e:
                msg = (f"attempts to publish attribute '{attr}' resulted in an "
                       f"unhandled error: {e}")
                _LOGGER.error(msg)

        with _GraphDatabase.driver(self.url, auth=self.auth) as driver:
            with driver.session() as session:
                _LOGGER.info('executing queries')
                for q in queries:
                    _LOGGER.debug('query: {}'.format(q))
                    session.run(q)

    # tag unification functions ------------------------------------------------
    def build_tag_normalization_interactive(self,
                                            include_currently_aliased=False):
        """for each tag in this tags object which isn't official, associate
        it with an official tag or create a new official tag to associate
        with

        """
        self.tag_normalization = []

        # candidates for normalization
        unofficial_tags = [t for t in self.tags
                           if t.label != OFFICIAL_TAG_LABEL]

        if not unofficial_tags:
            _LOGGER.info(
                'no un-official tags in this collection, nothing to normalize')
            return

        # split candidates into those that already have some associations
        # with official tags and those that have none
        tags_with_aliases = []
        tags_without_aliases = []
        with _GraphDatabase.driver(self.url, auth=self.auth) as driver:
            with driver.session() as session:
                for t in self.tags:
                    ((tags_with_aliases
                      if tag_is_alias(t, session)
                      else tags_without_aliases)
                     .append(t))

        # split unofficial tags into those we should process and those we
        # shouldn't
        should_process = {t.name: t for t in tags_without_aliases}

        if include_currently_aliased:
            should_process.update({t.name: t for t in tags_with_aliases})

        # build list of options we should alias
        tags_to_alias_options = list(should_process.items())

        # build list of official tags which can serve as an alias
        official_tag_options = [(t.name, t) for t in self.official_tags]

        # widgets
        tags_to_alias_dropdown = Dropdown(options=sorted(tags_to_alias_options))
        official_tag_dropdown = Dropdown(options=sorted(official_tag_options))
        new_official_tag_input = Text('')
        ignore_checkbox = Checkbox(False, description="don't alias",
                                   indent=False)
        continue_button = Button(description="alias")
        done_button = Button(description="alias and move on")
        output = Output()

        def update_official_tag_if_found(change):
            """if the selected tag in the dropdown is in the official tag
            dropdown, auto-select that

            """
            try:
                existing_official_val = [
                    value
                    for label, value in official_tag_dropdown.options
                    if label == change['new']
                ][0]
                official_tag_dropdown.value = existing_official_val
            except IndexError:
                return

        tags_to_alias_dropdown.observe(update_official_tag_if_found,
                                       names='label')

        def reset_widgets():
            new_official_tag_input.value = ''
            ignore_checkbox.value = False

        def make_alias(b):
            if ignore_checkbox.value:
                return

            queries_to_run = []
            if new_official_tag_input.value != '':
                _LOGGER.debug(f'new tag: {new_official_tag_input.value}')
                # new tag, create it and create the alias
                new_official_tag = NeoNode(name=new_official_tag_input.value,
                                           label=OFFICIAL_TAG_LABEL)

                with _GraphDatabase.driver(self.url, auth=self.auth) as driver:
                    with driver.session() as session:
                        _LOGGER.debug(new_official_tag.query)
                        session.run(new_official_tag.query)

                # refresh official tag options
                self.get_known_tags()
                official_tag_dropdown.options = sorted([
                    (t.name, t) for t in self.official_tags])

                new_alias_rel = NeoRelationship(
                    src=tags_to_alias_dropdown.value,
                    dst=new_official_tag,
                    _type='IS_ALIAS_OF')

                self.tag_normalization.append(new_alias_rel)
            else:
                self.tag_normalization.append(
                    NeoRelationship(src=tags_to_alias_dropdown.value,
                                    dst=official_tag_dropdown.value,
                                    _type='IS_ALIAS_OF'))

            reset_widgets()

        def register_done(b):
            done_with_tag_val = tags_to_alias_dropdown.value
            tags_to_alias_dropdown.options = [
                [label, value]
                for (label, value) in tags_to_alias_dropdown.options
                if value != done_with_tag_val]
            tags_to_alias_dropdown.value = tags_to_alias_dropdown.options[0][1]
            reset_widgets()

        continue_button.on_click(make_alias)
        done_button.on_click(make_alias)
        done_button.on_click(register_done)

        return display(tags_to_alias_dropdown,
                       official_tag_dropdown,
                       new_official_tag_input,
                       ignore_checkbox,
                       continue_button,
                       done_button,
                       output)

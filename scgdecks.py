#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: scgdecks.py
Author: zlamberty
Created: 2016-02-28

Description:
    SCG specific deck implementation

Usage:
    <usage>

"""

import datetime
import functools
import itertools
import json
import lxml.html
import os
import re
import requests
import yaml

import tqdm
import eri.logging as logging
import eri.html.utils

import common
import decks

from py2neo import Graph


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

RESULT_REGEX = r'^(?P<finish>\d+)(?:th|rd|st) place at \w+ on (?P<date>\d{1,2}/\d{1,2}/\d{2,4})$'
DECK_URL = 'http://sales.starcitygames.com//deckdatabase/deckshow.php?'
SCG_SESSION = None

INSERT_DECKS_QRY = """
UNWIND {decks} as deck
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
    d.url = deck.url
"""

INSERT_BOARDS_QRY = """
UNWIND {decks} as deck
MATCH (d:MtgDeck {id: deck.url})
WITH deck.mainboard as mainboard, deck.sideboard as sideboard, d
UNWIND mainboard as card
MATCH (c:MtgCard {id: card.cardname})
WITH card, d, c, sideboard
MERGE (d)<-[r:MAINBOARD]-(c)
  ON CREATE SET
    r.qty = card.qty
WITH sideboard, d
UNWIND sideboard as card
MATCH (c:MtgCard {id: card.cardname})
WITH card, d, c
MERGE (d)<-[r:SIDEBOARD]-(c)
  ON CREATE SET
    r.qty = card.qty
"""

logger = logging.getLogger(__name__)


# ----------------------------- #
#   utility functions           #
# ----------------------------- #

def require_scg_session(f):
    """decorator to require an SCG requests session and execute the function
    from within a context manager if that is not already the case

    """
    global SCG_SESSION

    @functools.wraps(f)
    def wrapped_f(*args, **kwargs):
        global SCG_SESSION
        if SCG_SESSION is None:
            logger.info("establishing a persistent connection for SCG requests")
            with requests.Session() as SCG_SESSION:
                return f(*args, **kwargs)
        else:
            # session must already be established
            return f(*args, **kwargs)

    return wrapped_f


class ScgDeckParseError(Exception):
    pass


# ----------------------------- #
#   deck defintions             #
# ----------------------------- #

class ScgDeck(decks.MtgDeck):
    """This will not be as simple as cards, since decks have a lot of meaningful
    metadata (e.g. tournament result, format, date, etc)

    This deck type is specific for decks as catalogued on the Star City Games
    deck database

    """
    @require_scg_session
    def __init__(self, url):
        """parse the SCG deck url into a deck object

        args:
            url: (string) url of the deck

        """
        self.url = url
        self.root = common.url2html(url, session=SCG_SESSION)
        self._author = None
        self._authorurl = None
        self._name = None
        self._event = None
        self._eventurl = None
        self._resultelem = None
        self._resulttext = None
        self._resultregmatch = None
        self._date = None
        self._finish = None
        self._mainboard = None
        self._sideboard = None

    @property
    def author(self):
        if self._author is None:
            try:
                self._author = self.root.cssselect('.player_name a')[0].text.lower()
            except:
                raise ScgDeckParseError("can't find author name")
        return self._author

    @property
    def authorurl(self):
        if self._authorurl is None:
            try:
                self._authorurl = self.root.cssselect('.player_name a')[0].get('href')
            except:
                raise ScgDeckParseError("can't find author url")
        return self._authorurl

    @property
    def name(self):
        if self._name is None:
            try:
                self._name = self.root.cssselect('.deck_title a')[0].text.lower()
            except:
                raise ScgDeckParseError("can't find deck name")
        return self._name

    @property
    def resultelem(self):
        if self._resultelem is None:
            try:
                self._resultelem = self.root.cssselect('.deck_played_placed')[0]
            except:
                raise ScgDeckParseError("can't find result element")
        return self._resultelem

    @property
    def resulttext(self):
        if self._resulttext is None:
            try:
                self._resulttext = self.resultelem.text_content().strip().lower()
            except:
                raise ScgDeckParseError("can't find result text")
        return self._resulttext

    @property
    def resultregmatch(self):
        if self._resultregmatch is None:
            try:
                self._resultregmatch = re.search(
                    RESULT_REGEX, self.resulttext
                ).groupdict()
            except:
                raise ScgDeckParseError("can't regex parse result text")
        return self._resultregmatch

    @property
    def event(self):
        if self._event is None:
            try:
                self._event = self.resultelem.find('a').text.lower()
            except:
                raise ScgDeckParseError("can't find event name")
        return self._event

    @property
    def eventurl(self):
        if self._eventurl is None:
            try:
                self._eventurl = self.resultelem.find('a').get('href')
            except:
                raise ScgDeckParseError("can't find event url")
        return self._eventurl

    @property
    def date(self):
        if self._date is None:
            try:
                self._date = datetime.datetime.strptime(
                    self.resultregmatch['date'], '%m/%d/%Y'
                )
            except:
                raise ScgDeckParseError("can't find event date")
        return self._date

    @property
    def finish(self):
        if self._finish is None:
            try:
                self._finish = int(self.resultregmatch['finish'])
            except:
                raise ScgDeckParseError("can't find event finishing place")
        return self._finish

    @property
    def mainboard(self):
        if self._mainboard is None:
            try:
                self._mainboard = {}
                for cardrow in self.root.cssselect('.decklist_heading+ ul li'):
                    qty = int(cardrow.text.lower().strip())
                    card = cardrow.find('a').text.lower()
                    self._mainboard[card] = qty
            except:
                raise ScgDeckParseError("can't find the deck mainboard")
        return self._mainboard

    @property
    def sideboard(self):
        if self._sideboard is None:
            try:
                self._sideboard = {}
                for cardrow in self.root.cssselect('.deck_sideboard li'):
                    qty = int(cardrow.text.lower().strip())
                    card = cardrow.find('a').text.lower()
                    self._sideboard[card] = qty
            except:
                raise ScgDeckParseError("can't find the deck sideboard")
        return self._sideboard

    def to_dict(self):
        return {
            'author': self.author,
            'authorurl': self.authorurl,
            'date': '{:%F}'.format(self.date),
            'event': self.event,
            'eventurl': self.eventurl,
            'finish': self.finish,
            'mainboard': [
                {'cardname': k, 'qty': v} for (k, v) in self.mainboard.items()
            ],
            'name': self.name,
            'sideboard': [
                {'cardname': k, 'qty': v} for (k, v) in self.sideboard.items()
            ],
            'url': self.url,
        }

    def to_json(self):
        return json.dumps(self.to_dict())


class ScgParseError(Exception):
    def __init__(self, msg):
        logger.error(msg)
        super().__init__()


@require_scg_session
def scg_decks(includeTest=False):
    return decks._get_decks(
        deckurls=scg_decklist_urls(includeTest=includeTest),
        decktype=ScgDeck
    )


@require_scg_session
def scg_decklist_urls(includeTest=False):
    """generator of urls for decklists on SCG's deck database

    args:
        includeTest: (bool) whether or not to include test decks (there are many)

    yields:
        urls of decks played in competitions

    raises:
        None

    """
    logger.info("collecting urls for scg decklists")
    for urlblock in tqdm.tqdm(scg_url_blocks()):
        resp = SCG_SESSION.get(urlblock)
        root = lxml.html.fromstring(resp.content)
        decklinks = root.cssselect('#content strong')
        eventtypes = root.cssselect('.deckdbbody2:nth-child(4) , .deckdbbody:nth-child(4)')
        if len(decklinks) != len(eventtypes):
            err = "Unequal numbers of decks and decktypes on block url {}"
            err = err.format(urlblock)
            raise ScgParseError(err)
        for (decklink, eventtype) in zip(decklinks, eventtypes):
            if eventtype.text != 'Test deck':
                yield decklink.getparent().get('href')


@require_scg_session
def scg_url_blocks():
    resp = SCG_SESSION.get(url=DECK_URL, params={'limit': 100})
    root = lxml.html.fromstring(resp.content)
    return [
        a.attrib['href'].replace('&limit=limit', '')
        for a in root.cssselect('tr:nth-child(106) a')
        if 'Next' not in a.text
    ]


def chunks(n, iterable):
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, n))
        if not chunk:
            return
        yield chunk


def load_decks_to_neo4j():
    graph = Graph(common.NEO4J_URL)

    # card name and set uniqueness
    graph.cypher.execute(
        "create constraint on (d:MtgDeck) assert d.id is unique"
    )

    logger.info('bulk loading to neo4j')
    for deckChunk in chunks(1000, scg_decks()):
        jsonChunk = []
        for d in deckChunk:
            try:
                jsonChunk.append(d.to_dict())
            except ScgDeckParseError:
                continue
        json_to_neo4j(jsonChunk, graph)


def json_to_neo4j(jsonChunk, graphCon):
    """neo4j can directly load json, we just have to get the query right. I
    think I have!

    args:
        jsonChunk: (json str) str representation of decks which will be unwound
            in cypher query spelled out below
        graphCon: (py2neo.Graph connection) connection to neo4j db into which we
            are upserting

    returns:
        None

    """
    graphCon.cypher.execute(INSERT_DECKS_QRY, parameters={'decks': jsonChunk})
    graphCon.cypher.execute(INSERT_BOARDS_QRY, parameters={'decks': jsonChunk})

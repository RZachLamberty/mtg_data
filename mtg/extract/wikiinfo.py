#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: wikiinfo.py
Author: zlamberty
Created: 2017-09-09

Description:
    utilities for parsing the mtg wiki at https://mtg.gamepedia.com/

Usage:
<usage>

"""

import logging
import re

import requests

# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

logger = logging.getLogger(__name__)

# tell requests to shut up
logging.getLogger('requests').setLevel(logging.WARN)
logging.getLogger('urllib3').setLevel(logging.WARN)


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def _keyword_urls():
    # two categories: keyword actions and keyword abilities
    for templatename in ['Template:Infobox action', 'Template:Infobox keyword']:
        url = 'https://mtg.gamepedia.com/api.php'
        resp = requests.get(url,
                            params={'action': 'query',
                                    'list': 'embeddedin',
                                    'eititle': templatename,
                                    'eilimit': 1000,
                                    'format': 'json'})
        j = resp.json()
        for item in j['query']['embeddedin']:
            yield item


def reminder_text():
    """get a dictionary of keyword: reminder text values (useful for text
    analytics)

    """
    remtext = {}
    for kwdict in _keyword_urls():
        kwname = kwdict['title'].lower()
        kwid = kwdict['pageid']
        try:
            resp = requests.get(url='https://mtg.gamepedia.com/api.php',
                                params={'action': 'parse',
                                        'pageid': kwid,
                                        'prop': 'wikitext',
                                        'format': 'json'})
            infobox = resp.json()['parse']['wikitext']['*']

            remtextnow = re.search('\| reminder = (.*)', infobox, re.I)
            remtextnow = remtextnow.groups()[0].lower()
            if remtextnow[-1] == '.':
                remtextnow = remtextnow[:-1]

            remtext[kwname] = remtextnow

            logger.debug('SUCCESS: {}'.format(kwname))
        except AttributeError:
            logger.debug('SUCCESS: {} (no reminder text)'.format(kwname))
        except Exception as e:
            logger.warning('FAILURE: {}'.format(kwname))
            logger.debug('\texception: {}'.format(e))

    return remtext

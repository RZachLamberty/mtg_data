#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: common.py
Author: zlamberty
Created: 2016-02-28

Description:
    common access values

Usage:
    <usage>

"""

import functools
import logging
import lxml.html
import os


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

# local html caching
HTML_DIR = os.path.join(os.sep, 'tmp', 'local_html_cache')

NEO4J_URL = os.environ.get('NEO4J_URL', 'http://neo4j:neo4j@localhost:7474/db/data')
logger = logging.getLogger(__name__)


# ----------------------------- #
#   utility                     #
# ----------------------------- #

def url2html(url, localdir=HTML_DIR, forcerefresh=False, hidden=True):
    """General purpose download tool; will save html files locally instead of
    making re-requests

    args:
        url: (str url) url to request
        localdir: (str pathname) directory in which we will save files
            (default: scrape.HTML_DIR)
        forcerefresh: (bool) whether or not we ignore local copy
        hidden: (bool) whether or not files are saved as hidden locally

    returns:
        lxml.html object

    raises:
        None

    """
    # what is the local name?
    urlbasename = os.path.basename(url)
    localname = os.path.join(
        localdir, '{}{}'.format(
            '.' if hidden else '',
            os.path.basename(url)
        )
    )

    # if we are calling out regardless (forcerefresh) or we have no local copy..
    if forcerefresh or not os.access(localname, os.R_OK):
        logger.debug('active download of url: {}'.format(url))
        resp = SCG_SESSION.get(url)
        with open(localname, 'wb') as f:
            f.write(resp.content)
        return lxml.html.fromstring(resp.content)
    else:
        with open(localname, 'rb') as f:
            return lxml.html.fromstring(f.read())

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

import logging
import os

import lxml.html
import requests


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

# local html caching
HTML_DIR = os.path.join(os.sep, 'var', 'data', 'local_html_cache')

LOGGER = logging.getLogger(__name__)


# ----------------------------- #
#   utility                     #
# ----------------------------- #

def url2html(url, localdir=HTML_DIR, forcerefresh=False, hidden=True,
             session=requests):
    """General purpose download tool; will save html files locally instead of
    making re-requests

    args:
        url (str): url to request
        localdir (str): directory in which we will save files
            (default: common.HTML_DIR)
        forcerefresh (bool): whether or not we ignore local copy
        hidden (bool): whether or not files are saved as hidden locally
        session (requests.Session): handy for multiple request scenarios

    returns:
        lxml.html: parsed xml object obtained from possibly-cached raw html

    raises:
        None

    """
    # what is the local name?
    localname = os.path.join(localdir,
                             '{}{}'.format('.' if hidden else '',
                                           os.path.basename(url)))

    # if we are calling out regardless (forcerefresh) or we have no local copy..
    if forcerefresh or not os.access(localname, os.R_OK):
        LOGGER.debug('active download of url: {}'.format(url))
        resp = session.get(url)
        with open(localname, 'wb') as fp:
            fp.write(resp.content)
        return lxml.html.fromstring(resp.content)
    else:
        with open(localname, 'rb') as fp:
            return lxml.html.fromstring(fp.read())

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: scryfall
Created: 2019-07-27

Description:

    code for extracting data from the scryfall api. documentation for this api
    is available at https://scryfall.com/docs/api

Usage:

    >>> import mtg.extract.scryfall

"""

import requests

from lxml import html


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

ENDPOINT = 'https://api.scryfall.com'
TAG_ENDPOINT = 'https://tagger.scryfall.com/card/{set:}/{collector_number:}'


# ----------------------------- #
#   tags                        #
# ----------------------------- #

def get_card_tags(set, collector_number, tag_endpoint=TAG_ENDPOINT):
    resp = requests.get(
        tag_endpoint.format(set=set, collector_number=collector_number))
    root = html.fromstring(resp.text)
    tag_hrefs = root.xpath('.//div[@class="illustration-tags"]/div/a/@href')
    return [href.split('/')[-1]
            for href in tag_hrefs
            if href.startswith('/tag/card')]

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: scrape.py
Author: zlamberty
Created: 2016-02-14

Description:


Usage:
<usage>

"""

import argparse
import os
import yaml

import eri.logging as logging

import cards
import common
import scgdecks


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

# logging and file IO constants
logging.getLogger("requests").setLevel(logging.WARNING)
logger = logging.getLogger("scrape")
logging.configure()


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def main(decksrc='scg', neo4jurl=common.NEO4J_URL):
    """do ery ol thang

    args:
        decksrc: string, the source of deck database elements we should parse
            into json for loading into our neo4j database. currently, only
            "scg" is a supported option (default: scg)
        neo4jurl: string, the url of the neo4j database into which we will load
            card and deck info (default: common.NEO4J_URL)

    returns: Nothing

    raises:
        ValueError: unhandled decksrc value

    """
    cards.json_to_neo4j()
    if decksrc =='scg':
        scgdecks.load_decks_to_neo4j()
    else:
        raise ValueError(
            "decksrc '{}' is not a valid deck src enumeration".format(decksrc)
        )


# ----------------------------- #
#   Command line                #
# ----------------------------- #

def parse_args():
    """ Take a log file from the commmand line """
    parser = argparse.ArgumentParser()

    decksrc = "type of deck source we are using"
    parser.add_argument("-d", "--decksrc", help=decksrc, default='scg')

    neo4jurl = "url of the neo4j database"
    parser.add_argument(
        "-u", "--neo4jurl", help=neo4jurl, default=common.NEO4J_URL
    )

    args = parser.parse_args()

    logger.debug("arguments set to {}".format(vars(args)))

    return args


if __name__ == '__main__':
    args = parse_args()
    main()

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
import logging
import logging.config
import os
import yaml

import cards
import common
import scgdecks


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

# logging and file IO constants
HERE = os.path.dirname(os.path.realpath(__file__))
logging.getLogger("requests").setLevel(logging.WARNING)
logger = logging.getLogger("scrape")
LOGCONF = os.path.join(HERE, 'logging.yaml')
with open(LOGCONF, 'rb') as f:
    logging.config.dictConfig(yaml.load(f))

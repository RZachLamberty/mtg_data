#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: config
Created: 2019-07-13

Description:

    shared configurations for this mtg module

Usage:

    >>> import config

"""

import os

PKG_ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
F_LOGGING_CONFIG = os.path.join(PKG_ROOT_DIR, 'logging.yaml')

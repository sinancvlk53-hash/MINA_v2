# -*- coding: utf-8 -*-
"""Geriye uyumluluk: kök dizindeki main.py tek motordur."""

import os
import runpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
runpy.run_path(os.path.join(_ROOT, "main.py"), run_name="__main__")

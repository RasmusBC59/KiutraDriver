
import time
from bisect import bisect
from typing import Any, ClassVar, Dict, List, Optional, Sequence

import numpy as np

from qcodes import validators as vals
from qcodes.instrument import ChannelList, InstrumentChannel, Instrument
from qcodes.parameters import Group, GroupParameter


class Kiutra(Instrument):
    def __init__(name: str, address: str, **kwargs: Any):
        super().__init__(name, address, **kwargs)

class Output(InstrumentChannel):
        def __init__(
            self,
            parent: "Kiutra",
            output_name: str,
            output_index: int):
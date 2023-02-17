
import time
from bisect import bisect
from typing import Any, ClassVar, Dict, List, Optional, Sequence

import numpy as np

from qcodes import validators as vals
from qcodes.instrument import ChannelList, InstrumentChannel, Instrument
from qcodes.parameters import Parameter, Group, GroupParameter


class Kiutra(Instrument):
    def __init__(name: str, address: str, **kwargs: Any):
        super().__init__(name, **kwargs)
        host = adress
        client = KiutraClient(host, 1006)
        print(client.query('cryostat.status'))



class Magnetigfield(Parameter):
    __init__(name, host, **kwargs):    
    sample_magnet = MagnetControl('sample_magnet', host)
        
    def get_raw(self):
        npts = self.root_instrument.npts()
        dt = self.root_instrument.dt()

class Output(InstrumentChannel):
        def __init__(
            self,
            parent: "Kiutra",
            output_name: str,
            output_index: int):
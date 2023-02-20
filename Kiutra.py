import time
from kiutra_api.api_client import KiutraClient
from typing import Any, ClassVar, Dict, List, Optional, Sequence
from kiutra_api.controller_interfaces import (
    ContinuousTemperatureControl,
    MagnetControl,
    ADRControl,
)
from qcodes import validators as vals
from qcodes.instrument import ChannelList, InstrumentChannel, Instrument
from qcodes.parameters import Parameter, Group, GroupParameter


class Kiutra(Instrument):
    def __init__(self, name: str, address: str, **kwargs: Any):
        super().__init__(name, **kwargs)
        self.host = address
        self.client = KiutraClient(self.host, 1006)
        print(client.query("cryostat.status"))

        self.add_parameter('magnetic_field',
                           label = "Magnetic field",
                           unit = "T",
                           parameter_class=MagneticField
        )
                               
        self.add_parameter('temperature',
                           label = 'Temperature',
                           unit = 'K',
                           parameter_class=TemperatureControl)    

class MagneticField(Parameter):
    def __init__(self, name, host, **kwargs):
        self.super.__init__(name, **kwargs)
        self.field_ramp = 0.5
        self.sample_magnet = MagnetControl("sample_magnet", self.root_instrument.host)

    def get_raw(self):
        return self.sample_magnet.field

    def set_raw(self, value: float) -> None:
        self.sample_magnet.start((value, self.field_ramp))
        while True:
            B = self.sample_magnet.field
            stable = self.sample_magnet.stable
            _, status = self.sample_magnet.status
            print(f"B = {B:.3f} ({status}, stable={stable})")
            if stable:
                break
            time.sleep(1)

class TemperatureControl(Parameter):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.temperature_control = ContinuousTemperatureControl('temperature_control', self.root_instrument.host)
        self.temperature_ramp
        
    def set_raw(self, value:float) -> None:
        self.temperature_control.start((value, self.temperature_ramp))
        print(f"Waiting for {self.temperature_ramp} K ")
        while True:
            ramping_info = self.temperature_control.get_ramping_info()

            T = self.temperature_control.kelvin
            print(f'T = {T:.3f} K)
            if ramping_info['ramp_done'] and ramping_info['ready_to_ramp']:
                # when whole ramp is covered, go on
                break
            time.sleep(1)
        
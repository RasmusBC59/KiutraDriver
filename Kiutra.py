import time
from typing import Any

from kiutra_api.api_client import KiutraClient
from kiutra_api.controller_interfaces import (
    ADRControl,
    ContinuousTemperatureControl,
    MagnetControl,
)
from qcodes import validators as vals
from qcodes.dataset import Measurement
from qcodes.instrument import Instrument
from qcodes.parameters import Parameter, ParameterBase


class KiutraIns(Instrument):
    def __init__(self, name: str, address: str, **kwargs: Any):
        super().__init__(name, **kwargs)
        self.host = address
        self.client = KiutraClient(self.host, 1006)
        print(self.client.query("cryostat.status"))

        self.add_parameter(
            "magnetic_field",
            label="Magnetic field",
            unit="T",
            parameter_class=MagneticField,
            vals=vals.Numbers(0.0, 4),
        )

        self.add_parameter(
            "magnetic_field_ramp",
            label="Field Ramp",
            unit="T/min",
            vals=vals.Numbers(0.01, 1.0),
        )

        self.add_parameter(
            "temperature",
            label="Temperature",
            unit="K",
            parameter_class=TemperatureControl,
            vals=vals.Numbers(0.1, 300),
        )

        self.add_parameter(
            "temperature_ramp",
            label="Temperature Ramp",
            unit="K/min",
            vals=vals.Numbers(0.01, 4.0),
        )


class MagneticField(Parameter):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.sample_magnet = MagnetControl("sample_magnet", self.root_instrument.host)

    def get_raw(self):
        return self.sample_magnet.field

    def set_raw(self, value: float) -> None:
        self.sample_magnet.start((value, self.root_instrument.magnetic_field_ramp()))
        while True:
            self._get_info()
            self._print_info()
            if self.stable:
                break
            time.sleep(1)

    def _get_info(self) -> None:
        self.B = self.sample_magnet.field
        self.stable = self.sample_magnet.stable
        _, self.status = self.sample_magnet.status

    def _print_info(self) -> None:
        print(f"B = {self.B:.3f} ({self.status}, stable={self.stable})")

    def sweep(self, start: float, end: float):
        ramp = self.root_instrument.magnetic_field_ramp()
        self.set_raw(start)
        print(f"Starts sweep from {start} T to {end} T ramping {ramp} T/min")
        self.sample_magnet.start((end, self.root_instrument.magnetic_field_ramp()))


class TemperatureControl(Parameter):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.temperature_control = ContinuousTemperatureControl(
            "temperature_control", self.root_instrument.host
        )

    def get_raw(self):
        return self.temperature_control.kelvin

    def set_raw(self, value: float) -> None:
        self.temperature_control.start((value, self.root_instrument.temperature_ramp()))
        print(f"Waiting for {value} K ")
        while True:
            self._get_info()
            self._print_info()
            if self._is_done():
                break
            time.sleep(1)

    def _get_info(self) -> None:
        self.ramping_info = self.temperature_control.get_ramping_info()
        self.T = self.temperature_control.kelvin

    def _print_info(self) -> None:
        print(f"T = {self.T:.3f} K")
        print(self.ramping_info)

    def _is_done(self) -> bool:
        return self.ramping_info["ramp_done"] and self.ramping_info["ready_to_ramp"]


def SweepMeasurement(
    kiutra: KiutraIns,
    start: float,
    end: float,
    ramp: float,
    write_period: float,
    *param_meas,
):
    meas = Measurement()
    meas.write_period = write_period
    meas.register_parameter(kiutra.magnetic_field)
    params = []
    for param in param_meas:
        if issubclass(param, ParameterBase):
            params.append(param)
            meas.register_parameter(param, setpoints=(kiutra.magnetic_field,))

    kiutra.magnetic_field_ramp(ramp)

    with meas.run() as datasaver:
        kiutra.sample_magnet.sweep(start, end, ramp)
        stable = False
        while not stable:
            stable = kiutra.magnetic_field.sample_magnet.stable
            B_1 = kiutra.magnetic_field.sample_magnet.field
            params_get = [(param, param.get()) for param in params]
            B_2 = kiutra.magnetic_field.sample_magnet.field
            datasaver.add_result(
                (kiutra.magnetic_field, (B_1 + B_2) / 2.0), *params_get
            )

        return datasaver.dataset

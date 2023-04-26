import time
from typing import Any

from kiutra_api.api_client import KiutraClient
from kiutra_api.controller_interfaces import (
    ADRControl,
    ContinuousTemperatureControl,
    MagnetControl,
    SampleControl,
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
            initial_value=0.1,
            set_cmd = lambda x: x
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
            initial_value=0.1,
            set_cmd = lambda x: x
        )

        self.add_parameter(
            "loader",
            label="Sample Loader",
            parameter_class=SampleLoader,
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

    def sweep(self, start: float, end: float):
        ramp = self.root_instrument.temperature_ramp()
        self.set_raw(start)
        print(f"Starts sweep from {start} K to {end} K ramping {ramp} K/min")
        self.sample_magnet.start((end, self.root_instrument.temperature_ramp()))


def BSweepMeasurement(
    kiutra: KiutraIns,
    start: float,
    end: float,
    ramp: float,
    delay: float,
    write_period: float,
    *param_meas,
):
    meas = Measurement()
    meas.write_period = write_period
    meas.register_parameter(kiutra.magnetic_field)
    params = []
    for param in param_meas:
        if isinstance(param, ParameterBase):
            params.append(param)
            meas.register_parameter(param, setpoints=(kiutra.magnetic_field,))

    kiutra.magnetic_field_ramp(ramp)

    with meas.run() as datasaver:
        kiutra.magnetic_field.sweep(start, end)
        stable = False
        B_2 = start
        while all((not stable, B_2 < end)):
            stable = kiutra.magnetic_field.sample_magnet.stable
            B_1 = kiutra.magnetic_field.sample_magnet.field
            params_get = [(param, param.get()) for param in params]
            B_2 = kiutra.magnetic_field.sample_magnet.field
            datasaver.add_result(
                (kiutra.magnetic_field, (B_1 + B_2) / 2.0), *params_get
            )
            time.sleep(delay)

        return datasaver.dataset


def TSweepMeasurement(
    kiutra: KiutraIns,
    start: float,
    end: float,
    ramp: float,
    delay: float,
    write_period: float,
    *param_meas,
):
    meas = Measurement()
    meas.write_period = write_period
    meas.register_parameter(kiutra.temperature)
    params = []
    for param in param_meas:
        if isinstance(param, ParameterBase):
            params.append(param)
            meas.register_parameter(param, setpoints=(kiutra.temperature,))

    kiutra.temperature_ramp(ramp)

    with meas.run() as datasaver:
        kiutra.temperature.sweep(start, end)
        stable = False
        T_2 = start
        while all((not stable, T_2 < end)):
            stable = kiutra.temperature.stable
            T_1 = kiutra.temperature.get_raw()
            params_get = [(param, param.get()) for param in params]
            T_1 = kiutra.temperature.get_raw()
            datasaver.add_result(
                (kiutra.temperature, (T_1 + T_2) / 2.0), *params_get
            )
            time.sleep(delay)

        return datasaver.dataset


class SampleLoader(Parameter):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.sample_loader = SampleControl(
            "sample_loader", self.root_instrument.host
            )

    def get_raw(self) -> tuple:
        return self.sample_loader.status
    
    def load(self) -> str:
        self.sample_loader.load_sample()
        print("Kiutra has started loading the sample")
        while self.sample_loader.progress < 1: # check whether progress is given in percent or decimal
            print("Loading is %.0f completed" % 100 * self.sample_loader.progress)
            time.sleep(1)
        return "Loading complete"

    def unload(self) -> None:
        self.sample_loader.unload_sample()
        print("Kiutra has started unloading the sample")
        while self.sample_loader.progress < 1: # check if progress is gives a meaningful number when unloading
            print("Unloading is %.0f completed" % 100 * self.sample_loader.progress)
            time.sleep(1)
        return "Unloading complete"
    
    def vent(self) -> None:
        self.sample_loader.open_airlock()

    def evac_chamber(self) -> None:
        self.sample_loader.close_airlock()

    def blockings(self) -> None:
        if self.sample_loader.is_blocked == True:
            return self.sample_loader.is_blocked_by() # check whether this is a callable or not
        
    def _reset(self) -> None:
        self.sample_loader.reset()


    # Maybe it is just easier to just set up the qdac immidiately \
    # after loading has completed in a detached piece of code
    # 
    # def load_cool_in_configuration(self, *cooling_configuration) -> None:
    #     self.load()
    #     params = []
    #     for param in cooling_configuration:
    #         if isinstance(param, ParameterBase):
    #             params.append(param)
    #             meas.register_parameter(param, setpoints=(kiutra.temperature,))
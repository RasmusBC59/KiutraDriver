import time
from typing import Any, Optional

import numpy as np
from qcodes import validators as vals
from qcodes.dataset import Measurement
from qcodes.instrument import Instrument
from qcodes.parameters import Parameter, ParameterBase


from kiutra_api.api_client import KiutraClient
from kiutra_api.controller_interfaces import (
    ADRControl,
    ContinuousTemperatureControl,
    MagnetControl,
    SampleControl,
)


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
            "magnetic_field_rate",
            label="Field Rate",
            unit="T/min",
            vals=vals.Numbers(0.01, 1.0),
            initial_value=0.1,
            set_cmd=lambda x: x,
        )

        self.add_parameter(
            "temperature",
            label="Temperature",
            unit="K",
            parameter_class=TemperatureControl,
            vals=vals.Numbers(0.1, 300),
        )

        self.add_parameter(
            "temperature_rate",
            label="Temperature Rate",
            unit="K/min",
            vals=vals.Numbers(0.01, 4.0),
            initial_value=0.1,
            set_cmd=lambda x: x,
        )

        self.add_parameter(
            "adr",
            label="ADR Control",
            unit="K",
            vals=vals.Numbers(0.1, 300),
            parameter_class=ADR_Temperature,
        )

        self.add_parameter(
            "operation_mode",
            label="Operation mode",
            get_cmd=self.adr.get_mode,
            vals=vals.Strings(),
        )

        self.add_parameter(
            "loader",
            label="Loader",
            parameter_class=SampleLoader,
            vals=vals.Numbers(0, 1),
        )

        self.add_parameter(
            "controllers",
            label="Controller Status",
            get_cmd=self.print_controller_status,
        )

    def print_controller_status(
        self,
    ) -> None:
        true_to_active = {True: "active", False: "inactive"}
        print(
            "Sample Magnet: {:>10}".format("")
            + f"{true_to_active[self.magnetic_field._is_active()]}\n"
            "Temperature control: {:>4}".format("")
            + f"{true_to_active[self.temperature._is_active()]}\n"
            "ADR control: {:>12}".format("")
            + f"{true_to_active[self.adr._is_active()]}\n"
            "Loader: {:>17}".format("")
            + f"{true_to_active[self.loader._is_active()]}\n"
        )


class MagneticField(Parameter):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.sample_magnet = MagnetControl("sample_magnet", self.root_instrument.host)
        assert isinstance(self.root_instrument, KiutraIns)

    def get_raw(self) -> float:
        return self.sample_magnet.field

    def set_raw(self, value: float) -> None:
        if self.sample_magnet.is_blocked is True:
            raise ValueError(
                f"End the following control sequences before \
                    setting the magnet: {self.get_blocks()}"
            )
        self.sample_magnet.start((value, self.root_instrument.magnetic_field_rate()))
        while True:
            self._get_info()
            self._print_info(value)
            if self.sample_magnet.stable:
                break
            time.sleep(1)

    def _get_info(self) -> None:
        self.B = self.sample_magnet.field
        self.stable = self.sample_magnet.stable

    def _print_info(self, setpoint: float) -> None:
        up_down = {True: "up", False: "down"}
        print(
            f"B = {self.B:.3f}T (sweeping {up_down[self.B < setpoint]} \
            to {setpoint}T, stable={self.stable})",
            end="\r",
        )

    def sweep(self, start: float, end: float, rate: Optional[float] = None) -> None:
        self.set_rate_if_not_None(rate)
        rate = self.root_instrument.magnetic_field_rate()
        print(f"Starts sweep from {start} T to {end} T ramping {rate} T/min")
        self.sample_magnet.start((end, rate))

    def set_rate_if_not_None(self, rate: Optional[float]):
        if rate is not None:
            self.root_instrument.magnetic_field_rate(rate)

    def get_blocks(self) -> str:
        return self.sample_magnet.is_blocked_by

    def interrupt(self) -> str:
        self.sample_magnet.stop()
        return "Sample magnet operation ended"

    def _is_active(self) -> bool:
        return self.sample_magnet.is_active


class TemperatureControl(Parameter):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.temperature_control = ContinuousTemperatureControl(
            "temperature_control", self.root_instrument.host
        )

    def get_raw(self) -> float:
        return self.temperature_control.kelvin

    def set_raw(self, value: float) -> None:
        if self.temperature_control.is_blocked is True:
            raise ValueError(
                f"End the following control sequences before \
                    setting the temperature: {self.get_blocks()}"
            )
        if self.check_range(value) is True:
            self.temperature_control.start(
                (value, self.root_instrument.temperature_rate())
            )
            while True:
                self._get_info()
                self._print_info(value)
                if self.temperature_control.stable:
                    break
                time.sleep(1)

    def check_range(self, T: float) -> bool:
        self.mode = self.get_mode()
        if T < 0.3 and self.mode == "cadr":
            raise ValueError(
                "Temperatures below 0.3K are not possible in continuous ADR mode"
            )
        return True

    def _get_info(self) -> None:
        self.setpoint = self.temperature_control.internal_setpoint
        self.stable = self.temperature_control.stable
        self.T = self.temperature_control.kelvin

    def _print_info(self, setpoint: float) -> None:
        up_down = {True: "up", False: "down"}
        print(
            f"T = {self.T:.3f}K (sweeping {up_down[self.T < setpoint]} \
            to {setpoint}K, stable={self.stable})"
        )

    def _is_done(self) -> bool:
        return self.ramping_info["ramp_done"] and self.ramping_info["ready_to_ramp"]

    def sweep(self, start: float, end: float, rate: Optional[float] = None) -> None:
        self.set_rate_if_not_None(rate)
        if self.check_range(end) is True:
            rate = self.root_instrument.temperature_rate()
            print(f"Starts sweep from {start} K to {end} K ramping {rate} K/min")
            self.temperature_control.start((end, rate))

    def set_rate_if_not_None(self, rate: Optional[float]):
        if rate is not None:
            self.root_instrument.temperature_rate(rate)

    def get_mode(self) -> str:
        return self.root_instrument.operation_mode()

    def get_blocks(self) -> str:
        return self.temperature_control.is_blocked_by

    def interrupt(self) -> str:
        self.temperature_control.stop()
        return "Temperature Control has ended"

    def _is_active(self) -> bool:
        return self.temperature_control.is_active


class ADR_Temperature(Parameter):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.adr_control = ADRControl("adr_control", self.root_instrument.host)

    def get_raw(self) -> float:
        return self.adr_control.kelvin

    def set_raw(
        self,
        value: float,
        rate: Optional[float] = None,
        adr_mode: Optional[int] = None,
        operation_mode: Optional[str] = None,
        auto_regenerate: bool = False,
        pre_regenerate: bool = False,
    ) -> None:
        if self.adr_control.is_blocked:
            raise ValueError(
                f"End the following control sequences before \
                    setting the temperature: {self.get_blocks()}"
            )

        if operation_mode is None:
            operation_mode = self.get_mode()

        self.set_rate_if_not_None(rate)

        if self.check_range(value, operation_mode) is True:
            rate = self.root_instrument.temperature_rate()
            self.adr_control.start_adr(
                setpoint=value,
                ramp=rate,
                adr_mode=adr_mode,
                operation_mode=operation_mode,
                auto_regenerate=auto_regenerate,
                pre_regenerate=pre_regenerate,
            )
            while True:
                self._get_info()
                self._print_info(value)
                if self.adr_control.stable:
                    break
                time.sleep(1)

    def sweep(
        self,
        start: float,
        value: float,
        rate: Optional[float] = None,
        adr_mode: Optional[int] = None,
        operation_mode: Optional[str] = None,
        auto_regenerate: bool = False,
        pre_regenerate: bool = False,
    ) -> None:
        if self.adr_control.is_blocked:
            raise ValueError(
                f"End the following control sequences before \
                    setting the temperature: {self.get_blocks()}"
            )

        if operation_mode is None:
            operation_mode = self.get_mode()

        self.set_rate_if_not_None(rate)

        if self.check_range(value, operation_mode) is True:
            rate = self.root_instrument.temperature_rate()
            print(f"Starts sweep from {start} K to {value} K ramping {rate} K/min")
            self.adr_control.start_adr(
                setpoint=value,
                ramp=rate,
                adr_mode=adr_mode,
                operation_mode=operation_mode,
                auto_regenerate=auto_regenerate,
                pre_regenerate=pre_regenerate,
            )

    def check_range(self, value: float, mode: Optional[str] = None) -> bool:
        self.assign_mode(mode)
        if value < 0.3 and self.mode == "cadr":
            raise ValueError(
                f"Temperatures below 0.3K are not possible in continuous ADR mode: \
                    use KiutraIns.adr({value}, "
                + 'operation_mode="adr")'
            )
        return True

    def assign_mode(self, mode: Optional[str]) -> None:
        self.mode = self.get_mode() if mode is None else mode

    def set_rate_if_not_None(self, rate: Optional[float]):
        if rate is not None:
            self.root_instrument.temperature_rate(rate)

    def get_mode(self) -> str:
        return self.adr_control.operation_mode

    def _get_info(self) -> None:
        self.stable = self.adr_control.stable
        self.T = self.adr_control.kelvin

    def _print_info(self, setpoint: float) -> None:
        up_down = {True: "up", False: "down"}
        print(
            f"T = {self.T:.3f}K (sweeping {up_down[self.T < setpoint]} \
            to {setpoint}K, stable={self.stable})"
        )

    def get_blocks(self) -> str:
        return self.adr_control.is_blocked_by

    def interrupt(self) -> str:
        self.adr_control.stop()
        return "ADR Control has ended"

    def _is_active(self) -> bool:
        return self.adr_control.is_active


class SampleLoader(Parameter):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.sample_loader = SampleControl("sample_loader", self.root_instrument.host)

    def get_raw(self) -> str:
        true_to_connected = {True: "connected", False: "not connected"}
        return f"The puck is {true_to_connected[self.get_connection_status()]}"

    def get_connection_status(self) -> bool:
        return self.sample_loader.sample_loaded

    def get_loading_progress(self) -> float:
        return self.sample_loader.progress

    def interrupt(self) -> str:
        self.sample_loader.stop()
        return "Sample Loader Control has ended"

    def _is_active(self) -> bool:
        return self.sample_loader.is_active


def BSweepMeasurement(
    kiutra: KiutraIns,
    start: float,
    end: float,
    rate: float,
    delay: float,
    *param_meas,
    write_period: float = 5.0,
):
    meas = Measurement()
    meas.write_period = write_period
    meas.register_parameter(kiutra.magnetic_field)
    params = []
    for param in param_meas:
        if isinstance(param, ParameterBase):
            params.append(param)
            meas.register_parameter(param, setpoints=(kiutra.magnetic_field,))

    kiutra.magnetic_field_rate(rate)
    kiutra.magnetic_field(start)
    while not kiutra.magnetic_field.sample_magnet.stable:
        time.sleep(0.1)

    with meas.run() as datasaver:
        kiutra.magnetic_field.sweep(start, end, rate)
        stable = False
        B_2 = start
        while all((not stable, up_down_condition(B_2, start, end))):
            stable = kiutra.magnetic_field.sample_magnet.stable
            B_1 = kiutra.magnetic_field()
            params_get = [(param, param.get()) for param in params]
            B_2 = kiutra.magnetic_field()
            datasaver.add_result(
                (kiutra.magnetic_field, (B_1 + B_2) / 2.0), *params_get
            )
            time.sleep(delay)

        return datasaver.dataset


def TSweepMeasurement(
    kiutra: KiutraIns,
    start: float,
    end: float,
    rate: float,
    step_interval: float,
    *param_meas,
    step_mode: str = "time",
    write_period: float = 5.0,
):
    meas = Measurement()
    meas.write_period = write_period
    meas.register_parameter(kiutra.temperature)
    params = []
    for param in param_meas:
        if isinstance(param, ParameterBase):
            params.append(param)
            meas.register_parameter(param, setpoints=(kiutra.temperature,))

    kiutra.temperature_rate(rate)
    kiutra.temperature(start)
    while not kiutra.temperature.temperature_control.stable:
        time.sleep(0.1)

    with meas.run() as datasaver:
        kiutra.temperature.sweep(start, end, rate)
        N = int(abs(end - start) / step_interval)
        setpoints = np.linspace(end, start, N).tolist()
        stable = False
        T_2 = start
        while all((not stable, up_down_condition(T_2, start, end))):
            stable = kiutra.temperature.temperature_control.stable

            if step_mode == "temp":
                try:
                    next_setpoint = setpoints.pop()
                    if next_setpoint == start:
                        continue
                    else:
                        while all(
                            (not stable, up_down_condition(T_2, start, next_setpoint))
                        ):
                            T_2 = kiutra.temperature()
                            time.sleep(0.001)
                except IndexError:
                    break
            else:
                time.sleep(step_interval)

            T_1 = kiutra.temperature()
            params_get = [(param, param.get()) for param in params]
            T_2 = kiutra.temperature()
            datasaver.add_result((kiutra.temperature, (T_1 + T_2) / 2.0), *params_get)

        return datasaver.dataset


def ADRSweepMeasurement(
    kiutra: KiutraIns,
    start: float,
    end: float,
    rate: float,
    step_interval: float,
    *param_meas,
    write_period: float = 5.0,
    adr_mode: Optional[int] = None,
    operation_mode: Optional[str] = None,
    auto_regenerate: bool = False,
    pre_regenerate: bool = False,
):
    meas = Measurement()
    meas.write_period = write_period
    meas.register_parameter(kiutra.adr)
    params = []
    for param in param_meas:
        if isinstance(param, ParameterBase):
            params.append(param)
            meas.register_parameter(param, setpoints=(kiutra.adr,))

    kiutra.temperature_rate(rate)
    if abs(start - kiutra.adr()) > 0.001:
        kiutra.adr(start, operation_mode=operation_mode)
        while not kiutra.adr.adr_control.stable:
            time.sleep(0.1)

    with meas.run() as datasaver:
        kiutra.adr.sweep(
            start=start,
            value=end,
            rate=rate,
            adr_mode=adr_mode,
            operation_mode=operation_mode,
            auto_regenerate=auto_regenerate,
            pre_regenerate=pre_regenerate,
        )
        stable = False
        T_2 = start

        while all((not stable, up_down_condition(T_2, start, end))):
            stable = kiutra.adr.adr_control.stable
            T_1 = kiutra.adr()
            params_get = [(param, param.get()) for param in params]
            T_2 = kiutra.adr()
            datasaver.add_result(
                (kiutra.adr, (T_1 + T_2) / 2.0),
                *params_get,
            )
            time.sleep(step_interval)

        return datasaver.dataset


def up_down_condition(value: float, start: float, end: float) -> bool:
    if start != end:
        return 0 < np.sign(end - start) * (end - value)
    else:
        raise ValueError(f"start {start} and end {end} cannot be equal")

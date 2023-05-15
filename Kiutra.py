import time
from typing import Any

from kiutra_api.api_client import KiutraClient
from kiutra_api.controller_interfaces import (
    ADRControl,
    ContinuousTemperatureControl,
    MagnetControl,
    SampleControl,
    HeaterControl,
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
            "magnetic_field_rate",
            label="Field Rate",
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
            "temperature_rate",
            label="Temperature Rate",
            unit="K/min",
            vals=vals.Numbers(0.01, 4.0),
            initial_value=0.1,
            set_cmd = lambda x: x
        )

        self.add_parameter(
            "adr",
            label="ADR Control",
            unit="K",
            vals=vals.Numbers(0.1, 300),
            parameter_class=ADR_Control,
        )

        self.add_parameter(
            "mode",
            label="Operation mode",
            get_cmd=self.adr.get_mode,
            #set_cmd=self.adr.set_mode,
            vals=vals.Strings(),
        )

        self.add_parameter(
            "heater",
            label="Heater Control",
            unit="K",
            vals=vals.Numbers(0.1, 300),
            parameter_class=Heater_Control,
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
            get_cmd=self.get_controller_status,
        )

    
    def get_controller_status(self) -> str:
        if self.magnetic_field._is_active() == True:
            print("Sample magnet is active")
        elif self.magnetic_field._is_active() == False:
            print("Sample magnet is inactive")
        if self.temperature._is_active() == True:
            print("Temperature control is active")
        elif self.temperature._is_active() == False:
            print("Temperature control is inactive")
        if self.adr._is_active() == True:
            print("ADR control is active")
        elif self.adr._is_active() == False:
            print("ADR control is inactive")
        # if self.heater._is_active() == True:
        #     print("Heater control is active")
        # elif self.heater._is_active() == False:
        #     print("Heater control is inactive")
        if self.loader._is_active() == True:
            print("Loader is active")
        elif self.loader._is_active() == False:
            print("Loader is inactive")


class MagneticField(Parameter):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.sample_magnet = MagnetControl("sample_magnet", self.root_instrument.host)

    def get_raw(self) -> float:
        return self.sample_magnet.field

    def set_raw(self, value: float) -> None:
        if self.sample_magnet.is_blocked == True:
            raise ValueError(f"End the following control sequences before \
                    setting the temperature: {self.get_blocks()}")
        else:
            self.sample_magnet.start((value, self.root_instrument.magnetic_field_rate()))
            while True:
                self._get_info()
                self._print_info()
                if self.sample_magnet.stable:
                    break
                time.sleep(1)

    def _get_info(self) -> None:
        self.B = self.sample_magnet.field
        self.stable = self.sample_magnet.stable
        self.setpoint = self.sample_magnet.field_setpoint
        #_, self.status = self.sample_magnet.status

    def _print_info(self) -> None:
        if self.B > self.setpoint:
            print(f"B = {self.B:.3f}T (sweeping down to {self.setpoint}T, stable={self.stable})")
        if self.B < self.setpoint:
            print(f"B = {self.B:.3f}T (sweeping up to {self.setpoint}T, stable={self.stable})")

    def sweep(self, start: float, end: float) -> None:
        ramp = self.root_instrument.magnetic_field_rate()
        self.set_raw(start)
        print(f"Starts sweep from {start} T to {end} T ramping {ramp} T/min")
        self.sample_magnet.start((end, self.root_instrument.magnetic_field_rate()))

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
        if self.temperature_control.is_blocked == True:
            raise ValueError(f"End the following control sequences before \
                    setting the temperature: {self.get_blocks()}")
        else:
            if self.check_range(value) == True:
                self.temperature_control.start((value, self.root_instrument.temperature_rate()))
                while True:
                    self._get_info()
                    self._print_info()
                    if self.temperature_control.stable:
                        break
                    time.sleep(1)

    def check_range(self, T: float) -> bool:
        self.mode = self.get_mode()
        if T < 0.3:
            if self.mode == "cadr":
                raise ValueError("Temperatures below 0.3K are not possible in continuous ADR mode")
            else:
                return True
        else:
            return True

    def _get_info(self) -> None:
        self.setpoint = self.temperature_control.internal_setpoint
        self.stable = self.temperature_control.stable
        self.T = self.temperature_control.kelvin

    def _print_info(self) -> None:
        if self.T > self.setpoint:
            print(f"B = {self.T:.3f}K (sweeping down to {self.setpoint}K, stable={self.stable})")
        if self.T < self.setpoint:
            print(f"B = {self.T:.3f}K (sweeping up to {self.setpoint}K, stable={self.stable})")

    def _is_done(self) -> bool:
        return self.ramping_info["ramp_done"] and self.ramping_info["ready_to_ramp"]

    def sweep(self, start: float, end: float) -> None:
        ramp = self.root_instrument.temperature_rate()
        self.set_raw(start)
        print(f"Starts sweep from {start} K to {end} K ramping {ramp} K/min")
        self.temperature_control.start((end, self.root_instrument.temperature_rate()))
        self.set_raw(end)

    def get_mode(self) -> str:
        self.adr_control = ADRControl("adr_control", self.root_instrument.host)
        return self.adr_control.operation_mode
    
    # def set_mode(self, mode: str) -> str:
    #     self.adr_control = ADRControl("adr_control", self.root_instrument.host)
    #     self.adr_control.operation_mode(mode)
    #     return f"ADR mode is set to {self.get_mode()}"
    
    def get_blocks(self) -> str:
        return self.temperature_control.is_blocked_by
    
    def interrupt(self) -> str:
        self.temperature_control.stop()
        return "Temperature control operation ended"
    
    def _is_active(self) -> bool:
        return self.temperature_control.is_active
    

class ADR_Control(Parameter):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.adr_control = ADRControl(
            "adr_control", self.root_instrument.host
        )

    def get_raw(self) -> float:
        return self.adr_control.kelvin
    
    def set_raw(self, value: float,
                adr_mode: int=None,
                mode: str=None, 
                auto_regenerate: bool=False, 
                pre_regenerate: bool=False) -> None:
        if self.adr_control.is_blocked == True:
            raise ValueError(f"End the following control sequences before \
                    setting the temperature: {self.get_blocks()}")
        else:
            if self.check_range(value, mode) == True:
                self.adr_control.start_adr(value, 
                                            self.root_instrument.temperature_rate(),
                                            adr_mode=adr_mode, 
                                            operation_mode=mode,
                                            auto_regenerate=auto_regenerate,
                                            pre_regenerate=pre_regenerate)
                while True:
                    self._get_info()
                    self._print_info()
                    if self.adr_control.stable:
                        break
                    time.sleep(1)

    def check_range(self, value: float, mode: str=None) -> bool:
        if mode == None:
            self.mode = self.get_mode()
        else:
            self.mode = mode
        if value < 0.3:
            if self.mode == "cadr":
                raise ValueError(f"Temperatures below 0.3K are not possible in continuous ADR mode: use KiutraIns.adr({value}, " \
                                 + "operation_mode=\"single_shot\")")
            else:
                return True
        else:
            return True
        
    def get_mode(self) -> str:
        return self.adr_control.operation_mode
    
    # def set_mode(self, mode: str) -> str:
    #     self.adr_control.operation_mode(mode)
    #     return f"ADR mode is set to {self.get_mode()}"

    def sweep(self, start: float, 
              end: float,
              adr_mode: int=None,
              mode: str=None, 
              auto_regenerate: bool=False, 
              pre_regenerate: bool=False) -> None:
        ramp = self.root_instrument.temperature_rate()
        self.set_raw(start, operation_mode=mode)
        print(f"Starts sweep from {start} K to {end} K ramping {ramp} K/min")
        self.adr_control.start_adr(end, 
                                   self.root_instrument.temperature_rate(),
                                   adr_mode=adr_mode,
                                   operation_mode=mode,
                                   auto_regenerate=auto_regenerate,
                                   pre_regenerate=pre_regenerate)
        #self.set_raw(end)

    def _get_info(self) -> None:
        self.setpoint = self.adr_control.internal_setpoint
        self.stable = self.adr_control.stable
        self.T = self.adr_control.kelvin

    def _print_info(self) -> None:
        if self.T > self.setpoint:
            print(f"B = {self.T:.3f}K (sweeping down to {self.setpoint}K, stable={self.stable})")
        if self.T < self.setpoint:
            print(f"B = {self.T:.3f}K (sweeping up to {self.setpoint}K, stable={self.stable})")

    def get_blocks(self) -> str:
        return self.adr_control.is_blocked_by

    def interrupt(self) -> str:
        self.adr_control.stop()
        return "ADR control operation ended"
    
    def _is_active(self) -> bool:
        return self.adr_control.is_active
    

class Heater_Control(Parameter):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.heater_control = HeaterControl(
            "heater_control", self.root_instrument.host
        )
    
    def get_raw(self) -> float:
        return self.heater_control.kelvin
    
    def set_raw(self, value: float) -> None:
        if self.heater_control.is_blocked == True:
            raise ValueError(f"End the following control sequences before \
                    setting the temperature: {self.get_blocks()}")
        else:
            self.heater_control.start((value, self.root_instrument.temperature_rate()))
            while True:
                self._get_info()
                self._print_info()
                if self.heater_control.stable:
                    break
                time.sleep(1)

    def get_blocks(self) -> str:
        return self.heater_control.is_blocked_by

    def interrupt(self) -> str:
        self.heater_control.stop()
        return "Heater control operation ended"
    
    def _is_active(self) -> bool:
        return self.heater_control.is_active
    

def BSweepMeasurement(
    kiutra: KiutraIns,
    start: float,
    end: float,
    rate: float,
    delay: float,
    write_period: float=5.0,
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

    kiutra.magnetic_field_rate(rate)

    def B_condition(B: float, start: float, end: float) -> bool:
        if start < end:
            return B < end
        elif start > end:
            return B > end

    with meas.run() as datasaver:
        kiutra.magnetic_field.sweep(start, end)
        stable = False
        B_2 = start
        while all((not stable, B_condition(B_2, start, end))):
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
    rate: float,
    delay: float,
    write_period: float=5.0,
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

    kiutra.temperature_rate(rate)

    def T_condition(T: float, start: float, end: float) -> bool:
        if start < end:
            return T < end
        elif start > end:
            return T > end

    with meas.run() as datasaver:
        kiutra.temperature.sweep(start, end)
        stable = False
        T_2 = start
        while all((not stable, T_condition(T_2, start, end))):
            stable = kiutra.temperature.temperature_control.stable
            T_1 = kiutra.temperature.temperature_control.kelvin
            params_get = [(param, param.get()) for param in params]
            T_2 = kiutra.temperature.temperature_control.kelvin
            datasaver.add_result(
                (kiutra.temperature, (T_1 + T_2) / 2.0), *params_get
            )
            time.sleep(delay)

        return datasaver.dataset


def ADRSweepMeasurement(
    kiutra: KiutraIns,
    start: float,
    end: float,
    rate: float,
    delay: float,
    write_period: float=5.0,
    adr_mode: int=None,
    operation_mode: str=None, 
    auto_regenerate: bool=False, 
    pre_regenerate: bool=False,
    *param_meas,
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

    def T_condition(T: float, start: float, end: float) -> bool:
        if start < end:
            return T < end
        elif start > end:
            return T > end

    with meas.run() as datasaver:
        kiutra.adr.sweep(start, end, adr_mode, operation_mode, auto_regenerate, pre_regenerate)
        stable = False
        T_2 = start
        while all((not stable, T_condition(T_2, start, end))):
            stable = kiutra.adr.adr_control.stable
            T_1 = kiutra.adr.adr_control.kelvin
            params_get = [(param, param.get()) for param in params]
            T_2 = kiutra.adr.adr_control.kelvin
            datasaver.add_result(
                (kiutra.adr, (T_1 + T_2) / 2.0), *params_get
            )
            time.sleep(delay)

        return datasaver.dataset
    

class SampleLoader(Parameter):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.sample_loader = SampleControl("sample_loader", self.root_instrument.host)

    def get_raw(self) -> str:
        return f"The puck is connected: {self.get_connection_status()}"

    def get_connection_status(self) -> bool:
        return self.sample_loader.sample_loaded
    
    def get_loading_progress(self) -> float:
        return self.sample_loader.progress

    def interrupt(self) -> str:
        self.sample_loader.stop()
        return "Sample loader control operation ended"
    
    def _is_active(self) -> bool:
        return self.sample_loader.is_active